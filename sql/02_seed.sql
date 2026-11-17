/* Datos base (catálogos). Se puede ejecutar varias veces: solo inserta lo que falta. */
USE [nova_sound];
GO

-- Roles
INSERT INTO [Rol] ([Rol])
SELECT v.n FROM (VALUES ('Operador'), ('Inspector'), ('Gerente')) v(n)
WHERE NOT EXISTS (SELECT 1 FROM [Rol] r WHERE r.[Rol] = v.n);

-- Modelos
INSERT INTO [Modelo] ([Nombre])
SELECT v.n FROM (VALUES ('NS-MINI'), ('NS-SPORT'), ('NS-PRO'), ('NS-MAX')) v(n)
WHERE NOT EXISTS (SELECT 1 FROM [Modelo] m WHERE m.[Nombre] = v.n);

-- Líneas
INSERT INTO [Linea] ([NombreLinea])
SELECT v.n FROM (VALUES ('L-01'), ('L-02'), ('L-03')) v(n)
WHERE NOT EXISTS (SELECT 1 FROM [Linea] l WHERE l.[NombreLinea] = v.n);

-- Turnos (T1 05:00-14:00, T2 14:00-21:30)
IF NOT EXISTS (SELECT 1 FROM [Turno] WHERE [HorarioInicio] = '05:00' AND [HorarioFin] = '14:00')
    INSERT INTO [Turno] ([HorarioInicio], [HorarioFin]) VALUES ('05:00', '14:00');
IF NOT EXISTS (SELECT 1 FROM [Turno] WHERE [HorarioInicio] = '14:00' AND [HorarioFin] = '21:30')
    INSERT INTO [Turno] ([HorarioInicio], [HorarioFin]) VALUES ('14:00', '21:30');

-- Estados de pieza (los demás módulos mueven las piezas entre estos)
INSERT INTO [EstadoPieza] ([Estado])
SELECT v.n FROM (VALUES ('Ensamblada'), ('Pruebas Funcionales'), ('Aprobada'),
                        ('En retención'), ('En retrabajo'), ('Scrap'),
                        ('Empacada'), ('Embarcada')) v(n)
WHERE NOT EXISTS (SELECT 1 FROM [EstadoPieza] e WHERE e.[Estado] = v.n);
GO
