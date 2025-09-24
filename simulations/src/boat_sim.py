import torch
import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple, Optional
import matplotlib.pyplot as plt
import json
from pathlib import Path
from datetime import datetime

"""Torch Settings"""
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
DTYPE = torch.float64

"""Water Type"""
RHO = 1025.0  # 1025.0 for sea water and 1000 for freshwater


def _torch_interp1d(
    x: torch.Tensor, xp: torch.Tensor, fp: torch.Tensor
) -> torch.Tensor:
    """
    Linear interpolation like numpy.interp for 1D tensors.
    x:  shape [...], on same device/dtype as xp/fp (or broadcastable)
    xp: shape [N], strictly increasing
    fp: shape [N]
    Returns shape equal to x.
    """
    # Make sure x is tensor on same device/dtype
    if not isinstance(x, torch.Tensor):
        x = torch.tensor(x, dtype=DTYPE, device=xp.device)
    else:
        x = x.to(dtype=xp.dtype, device=xp.device)

    x = torch.clamp(x, xp[0], xp[-1])
    idx = torch.searchsorted(xp, x, right=True).clamp(1, xp.numel() - 1)
    x0, x1 = xp[idx - 1], xp[idx]
    y0, y1 = fp[idx - 1], fp[idx]
    t = (x - x0) / torch.clamp(x1 - x0, min=1e-12)
    return y0 + t * (y1 - y0)


def _trapz(y: torch.Tensor, x: torch.Tensor) -> torch.Tensor:
    """Trapezoidal integral of y(x)."""
    # Ensure matching device/dtype
    y = y.to(dtype=DTYPE)
    x = x.to(dtype=DTYPE)
    return torch.sum(0.5 * (y[1:] + y[:-1]) * (x[1:] - x[:-1]))


class Subsystem:
    def power(self, t_s: float, state: Dict) -> float:
        raise NotImplementedError()


@dataclass
class Battery:
    name: str
    capacity_Ah: float
    nominal_voltage: float
    internal_resistance_ohm: float = 0.02
    peukert_exponent: float = 1.05
    soc: float = 1.0
    capacity_Wh: float = field(init=False)
    energy_Wh_remaining: float = field(init=False)
    voc_curve: Optional[List[Tuple[float, float]]] = None  # [(SoC, Voc)]

    _voc_soc: torch.Tensor = field(init=False, repr=False)
    _voc_V: torch.Tensor = field(init=False, repr=False)

    def __post_init__(self):
        self.capacity_Wh = self.capacity_Ah * self.nominal_voltage
        self.energy_Wh_remaining = self.capacity_Wh * self.soc
        if self.voc_curve is None:
            self.voc_curve = [
                (0.0, 0.9 * self.nominal_voltage),
                (0.1, 0.95 * self.nominal_voltage),
                (0.2, self.nominal_voltage),
                (0.8, 1.03 * self.nominal_voltage),
                (1.0, 1.05 * self.nominal_voltage),
            ]
        self._voc_soc = torch.tensor(
            [p[0] for p in self.voc_curve], dtype=DTYPE, device=DEVICE
        )
        self._voc_V = torch.tensor(
            [p[1] for p in self.voc_curve], dtype=DTYPE, device=DEVICE
        )

    def open_circuit_voltage(self) -> float:
        soc = max(0.0, min(1.0, self.energy_Wh_remaining / self.capacity_Wh))
        voc_t = _torch_interp1d(
            torch.tensor(soc, dtype=DTYPE, device=DEVICE), self._voc_soc, self._voc_V
        )
        return float(voc_t.detach().cpu().item())

    def terminal_voltage(self, current_A: float) -> float:
        return max(
            0.0, self.open_circuit_voltage() - current_A * self.internal_resistance_ohm
        )

    def step(self, power_W: float, dt_s: float) -> Dict[str, float]:
        # 1-step voltage/current solve using Voc and Rint
        Voc = self.open_circuit_voltage()
        I_guess = power_W / max(1e-6, Voc)
        Vt = max(1e-6, Voc - self.internal_resistance_ohm * I_guess)
        current_A = power_W / Vt

        # Peukert adjustment at higher discharge rates
        C_rate = abs(current_A) / max(1e-6, self.capacity_Ah)
        peukert_factor = (
            (C_rate / (1 / 20)) ** (self.peukert_exponent - 1) if C_rate > 0 else 1.0
        )

        dE_Wh = (power_W * peukert_factor * dt_s) / 3600.0
        self.energy_Wh_remaining = max(0.0, self.energy_Wh_remaining - dE_Wh)
        self.soc = self.energy_Wh_remaining / self.capacity_Wh

        Vt = self.terminal_voltage(current_A)
        return {
            "current_A": current_A,
            "voltage_V": Vt,
            "soc": self.soc,
            "energy_Wh_remaining": self.energy_Wh_remaining,
        }


@dataclass
class ConstantLoad(Subsystem):
    name: str
    watts: float
    duty_cycle: float = 1.0

    def power(self, t_s: float, state: Dict) -> float:
        return self.watts * self.duty_cycle


@dataclass
class DutyCycledLoad(Subsystem):
    name: str
    watts_on: float
    period_s: float
    duty_cycle: float
    phase_s: float = 0.0

    def power(self, t_s: float, state: Dict) -> float:
        tau = (t_s + self.phase_s) % self.period_s
        return self.watts_on if tau < self.duty_cycle * self.period_s else 0.0


@dataclass
class MotorESC(Subsystem):
    name: str
    kv_rpm_per_V: float
    esc_efficiency: float = 0.95
    motor_efficiency: float = 0.85
    prop_diameter_m: float = 0.15
    prop_ct: float = 0.08
    prop_cp: float = 0.04
    rho: float = RHO
    max_voltage: float = 24.0
    throttle_fn: Optional[Callable[[float], float]] = None
    thrust_fn: Optional[Callable[[float], float]] = None

    def thrust_from_rpm(self, rpm: float) -> float:
        # T = Ct * rho * (n^2) * D^4   , n=rps
        n = rpm / 60.0
        D = self.prop_diameter_m
        return self.prop_ct * self.rho * (n**2) * (D**4)

    def power_from_rpm(self, rpm: float) -> float:
        # P_shaft = Cp * rho * (n^3) * D^5
        n = rpm / 60.0
        D = self.prop_diameter_m
        return self.prop_cp * self.rho * (n**3) * (D**5)

    def rpm_from_thrust(self, thrust_N: float) -> float:
        D = self.prop_diameter_m
        n = math.sqrt(max(0.0, thrust_N) / (self.prop_ct * self.rho * (D**4) + 1e-12))
        return n * 60.0

    def rpm_from_voltage_throttle(self, voltage_V: float, throttle: float) -> float:
        # No-load RPM ~ KV * V * throttle; reduce a bit for load
        rpm_nl = self.kv_rpm_per_V * voltage_V * throttle
        return max(0.0, rpm_nl * 0.8)

    def power(self, t_s: float, state: Dict) -> float:
        voltage_V = state.get("bus_voltage_V", 12.0)
        if self.thrust_fn is not None:
            thrust = max(0.0, float(self.thrust_fn(t_s)))
            rpm = self.rpm_from_thrust(thrust)
            shaft_W = self.power_from_rpm(rpm)
        else:
            throttle = max(
                0.0, min(1.0, float(self.throttle_fn(t_s) if self.throttle_fn else 0.0))
            )
            rpm = self.rpm_from_voltage_throttle(
                min(voltage_V, self.max_voltage), throttle
            )
            shaft_W = self.power_from_rpm(rpm)
        # electrical power in (divide by combined efficiency)
        return shaft_W / max(1e-3, self.motor_efficiency * self.esc_efficiency)


@dataclass
class BoatSim:
    battery: Battery
    subsystems: List[Subsystem]
    dt_s: float = 1.0
    t_s: float = 0.0
    log: Dict[str, List[float]] = field(
        default_factory=lambda: {
            "t_s": [],
            "power_W": [],
            "current_A": [],
            "voltage_V": [],
            "soc": [],
            "energy_Wh_remaining": [],
        }
    )

    def step(self):
        # state shares current bus voltage estimate
        state = {"bus_voltage_V": self.battery.open_circuit_voltage()}
        P_total = sum(max(0.0, s.power(self.t_s, state)) for s in self.subsystems)

        batt = self.battery.step(P_total, self.dt_s)
        self.t_s += self.dt_s

        # Log (Python lists for logs)
        self.log["t_s"].append(self.t_s)
        self.log["power_W"].append(P_total)
        self.log["current_A"].append(batt["current_A"])
        self.log["voltage_V"].append(batt["voltage_V"])
        self.log["soc"].append(batt["soc"])
        self.log["energy_Wh_remaining"].append(batt["energy_Wh_remaining"])
        return batt

    def run(self, duration_s: float):
        for _ in range(int(duration_s / self.dt_s)):
            last = self.step()
            if last["soc"] <= 0.0:
                break

    def plot_power(self, save_path: Optional[Path] = None):
        plt.figure()
        plt.plot(self.log["t_s"], self.log["power_W"])
        plt.xlabel("Time (s)")
        plt.ylabel("Total Power (W)")
        plt.title("Boat Power vs Time")
        plt.grid(True)
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.show()

    def plot_soc(self, save_path: Optional[Path] = None):
        plt.figure()
        plt.plot(self.log["t_s"], [s * 100 for s in self.log["soc"]])
        plt.xlabel("Time (s)")
        plt.ylabel("State of Charge (%)")
        plt.title("Battery SoC vs Time")
        plt.grid(True)
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.show()

    def plot_voltage_current(
        self,
        save_voltage_path: Optional[Path] = None,
        save_current_path: Optional[Path] = None,
    ):
        plt.figure()
        plt.plot(self.log["t_s"], self.log["voltage_V"])
        plt.xlabel("Time (s)")
        plt.ylabel("Bus Voltage (V)")
        plt.title("Battery Voltage vs Time")
        plt.grid(True)
        if save_voltage_path:
            plt.savefig(save_voltage_path, dpi=150, bbox_inches="tight")
        plt.show()

        plt.figure()
        plt.plot(self.log["t_s"], self.log["current_A"])
        plt.xlabel("Time (s)")
        plt.ylabel("Current (A)")
        plt.title("Battery Current vs Time")
        plt.grid(True)
        if save_current_path:
            plt.savefig(save_current_path, dpi=150, bbox_inches="tight")
        plt.show()

    def summary(self) -> Dict[str, float]:
        if not self.log["t_s"]:
            return {
                "mission_time_s": 0.0,
                "energy_used_Wh": 0.0,
                "energy_remaining_Wh": self.battery.energy_Wh_remaining,
                "soc_end": self.battery.soc,
            }
        t = torch.tensor(self.log["t_s"], dtype=DTYPE, device=DEVICE)
        p = torch.tensor(self.log["power_W"], dtype=DTYPE, device=DEVICE)
        total_Wh = float((_trapz(p, t) / 3600.0).detach().cpu().item())
        mission_time_s = float(t[-1].detach().cpu().item())
        return {
            "mission_time_s": mission_time_s,
            "energy_used_Wh": total_Wh,
            "energy_remaining_Wh": self.battery.energy_Wh_remaining,
            "soc_end": self.battery.soc,
        }

    def export_log(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
            json.dump(self.log, f, indent=2)

    def save_all_plots(self, log_dir: Path, prefix: str = "run"):
        """Save all plots into log_dir with a common prefix."""
        log_dir.mkdir(parents=True, exist_ok=True)
        self.plot_power(save_path=log_dir / f"{prefix}_power.png")
        self.plot_soc(save_path=log_dir / f"{prefix}_soc.png")
        self.plot_voltage_current(
            save_voltage_path=log_dir / f"{prefix}_voltage.png",
            save_current_path=log_dir / f"{prefix}_current.png",
        )


if __name__ == "__main__":
    # 12 V, 20 Ah pack
    battery = Battery(
        name="Main 12V",
        capacity_Ah=20.0,
        nominal_voltage=12.0,
        internal_resistance_ohm=0.03,  # TODO: test internal resistance
        peukert_exponent=1.05,
    )

    def thrust_fn(t: float) -> float:
        # 0 → 40 N over 2 minutes
        if t < 120:
            return 40.0 * (t / 120.0)
        # hold 40 N
        elif t < 1200:
            return 40.0
        # ramp down 40 → 0 N
        elif t < 1500:
            return 40.0 * (1.0 - (t - 1200.0) / 300.0)
        # sawtooth: 60 → 48 N with 12 s period
        elif t < 2000:
            return 60.0 - (t % 12.0)
        # ramp up 0 → 65 N (2000–2200)
        elif t < 2200:
            return 65.0 * ((t - 2000.0) / 200.0)
        # ramp down 65 → 0 N (2200–3600)
        elif t < 3600:
            return 65.0 * (1.0 - (t - 2200.0) / 1400.0)
        # 0 N (3600–3800)
        elif t < 3800:
            return 0.0
        # safe default after 3800
        else:
            return 0.0

    motor = MotorESC(
        name="Main Thruster",
        kv_rpm_per_V=600.0,
        esc_efficiency=0.93,
        motor_efficiency=0.85,
        prop_diameter_m=0.09,
        prop_ct=0.07,
        prop_cp=0.035,
        rho=1000.0,
        max_voltage=24.0,
        thrust_fn=thrust_fn,
    )

    telemetry = ConstantLoad("915MHz Telemetry Radio (Sik V3)", watts=1.2)
    gnss = ConstantLoad("GNSS Receiver (u-blox M10)", watts=0.35)
    fc = ConstantLoad("Flight Controller", watts=0.8)
    compass = ConstantLoad("Compass (QMC5883L)", watts=0.05)
    servo = DutyCycledLoad(
        "Steering Servo (25 kgcm)", watts_on=8.0, period_s=5.0, duty_cycle=0.2
    )

    sim = BoatSim(
        battery=battery,
        subsystems=[motor, telemetry, gnss, fc, compass, servo],
        dt_s=1.0,
    )

    # Run mission
    sim.run(duration_s=1 * (60 * 60))

    # Summary
    summary = sim.summary()
    print("Summary:", summary)

    # Logging/plots directory using pathlib
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logs_dir = Path("simulations") / "logs" / f"boat_run_{timestamp}"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Save JSON log
    sim.export_log(logs_dir / "boat_sim_log.json")

    # Save all plots
    sim.save_all_plots(log_dir=logs_dir, prefix="boat")

    print(f"Logs and plots saved to: {logs_dir.resolve()}")
