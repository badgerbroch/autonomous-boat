clear; clc;

% === PARAMETERS ===
side = 0.762;             % Square loop side [m]
I = 2;                   % Current [A]
mu0 = 4*pi*1e-7;          % Vacuum permeability [T·m/A]
Nxy = 40;                 % x-y grid resolution
Nz = 40;                  % z grid resolution
N = 62;                   % Number of turns in the loop

% === Grid Definitions ===
x = linspace(-1, 1, Nxy);
y = linspace(-1, 1, Nxy);
z = 100 * 0.3048;           % Convert 85 ft to meters
[X, Y] = meshgrid(x, y);
Z = ones(size(X)) * z;     % Constant depth plane

Bz = zeros(size(X));       % Field array at one z-slice

% === Loop Geometry ===
L = side / 2;
vertices = [
    -L -L 0;
     L -L 0;
     L  L 0;
    -L  L 0;
    -L -L 0
];

% === Compute Bz on the grid ===
for s = 1:4
    r1 = vertices(s, :);
    r2 = vertices(s+1, :);
    dl = r2 - r1;
    r_mid = (r1 + r2) / 2;

    Rx = X - r_mid(1);
    Ry = Y - r_mid(2);
    Rz = Z - r_mid(3);
    R_mag = sqrt(Rx.^2 + Ry.^2 + Rz.^2);
    R_mag(R_mag == 0) = Inf;  % Avoid division by zero

    dBz = (dl(1)*Ry - dl(2)*Rx);  % Only z-component
    factor = (mu0 * I) ./ (4 * pi * R_mag.^3);
    Bz = Bz + factor .* dBz;
end

% === Scale by number of turns ===
Bz = N * Bz;

% === 3D Contour Plot (x, y, Bz at fixed z) ===
figure;
contour3(X, Y, Bz, 500);
xlabel('x (m)');
ylabel('y (m)');
zlabel('Magnetic Field B_z (T)');
title('Magnetic Field B_z at 100 ft Depth');
colorbar;
colormap turbo;
view(3);

