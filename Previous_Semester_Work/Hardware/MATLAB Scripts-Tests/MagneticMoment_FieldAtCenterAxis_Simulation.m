
% Calculate Range given magnetic moment for free space, and seawater 
sW = 4      % Conductivity of sea water in s/m 
freq = 40 ;       % Frequency
mu = 4*pi*10^-7 ;
m = [1:1:41]*2.5 ; % Magnetic moment 
alpha = sqrt(pi*freq*mu*sW) % 1/(Skin depth)
Br = 0.2e-9;  % Field strength threshold 

rmax = power(mu*m./(2*pi*Br),1/3) ;     % Max range given field threshold (free space)

rmsw  = [1:1:41] ; % Define max range for sea water 
syms rm
for i = 1:41 
 mi = m(i); 
rmsw(i) = vpasolve(rm == power(mu*mi/(2*pi*Br)*exp(-alpha*rm),1/3),rm) ;  % Max range for sea water (Given different magnetic moments);
end   

plot(m,rmax,m,rmsw,'linewidth',4);
xlabel('Magnetic Moment [Am^{2}]')
ylabel('Maximum Range [m]')
legend('Free Space','Sea Water, Freq = 0.04 kHz')
xlim([0,100])
set(gca,'FontSize',25)
grid on 


Br = 1.32 % Remanent field of magnet (N42)
M = Br/mu   ;% Magnetization of magnet 
V = 0.03^3 % Volume of magnet 
m = M*V ;   % Magnetic moment 

r = 1  % Distance from source 
Brx_mag = mu*m/(2*pi*r^3)   % RX magnetic field in T

% Comparison with loop 
A = 0.46446917   % 2x2 ft square loop 
I = 1   % Input current 
N = 130 % Number of turns 
mloop = N*I*A 
