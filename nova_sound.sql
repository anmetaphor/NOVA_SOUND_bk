IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'nova_sound')
BEGIN
    CREATE DATABASE [nova_sound];
END
GO

USE [nova_sound];
GO


CREATE TABLE [Cliente] (
  [idCliente] INT IDENTITY(1,1) NOT NULL,
  [NombreCliente] VARCHAR(255) NOT NULL,
  [TipoCliente] VARCHAR(255) NOT NULL,
  PRIMARY KEY ([idCliente])
);

CREATE TABLE [Modelo] (
  [id] INT IDENTITY(1,1) NOT NULL,
  [Nombre] VARCHAR(255) NOT NULL,
  PRIMARY KEY ([id])
);

CREATE TABLE [Linea] (
  [idLinea] INT IDENTITY(1,1) NOT NULL,
  [NombreLinea] VARCHAR(20) NOT NULL,
  PRIMARY KEY ([idLinea])
);

CREATE TABLE [Turno] (
  [idTurno] INT IDENTITY(1,1) NOT NULL,
  [HorarioInicio] TIME NOT NULL,
  [HorarioFin] TIME NOT NULL,
  PRIMARY KEY ([idTurno])
);

CREATE TABLE [Usuario] (
  [id] INT IDENTITY(1,1) NOT NULL,
  [Usuario] VARCHAR(255) NOT NULL,
  [Contrasena] VARCHAR(255) NOT NULL,
  PRIMARY KEY ([id])
);

CREATE TABLE [Rol] (
  [id] INT IDENTITY(1,1) NOT NULL,
  [Rol] VARCHAR(50) NOT NULL,
  PRIMARY KEY ([id])
);

CREATE TABLE [EstadoPieza] (
  [idEstado] INT IDENTITY(1,1) NOT NULL,
  [Estado] VARCHAR(255) NOT NULL,
  PRIMARY KEY ([idEstado])
);

CREATE TABLE [Pedido] (
  [idPedido] INT IDENTITY(1,1) NOT NULL,
  [ClienteID] INT NOT NULL,
  [FechaPedido] DATETIME NOT NULL,
  [Estado] VARCHAR(20) NOT NULL CHECK ([Estado] IN ('Finalizado', 'En proceso', 'Cancelado')),
  [FechaCompromiso] DATE NOT NULL,
  PRIMARY KEY ([idPedido]),
  FOREIGN KEY ([ClienteID]) REFERENCES [Cliente] ([idCliente])
);

CREATE TABLE [DetallePedido] (
  [idDetalle] INT IDENTITY(1,1) NOT NULL,
  [idPedido] INT NOT NULL,
  [idModelo] INT NOT NULL,
  [Color] VARCHAR(50) NOT NULL,
  [CantidadSolicitada] INT NOT NULL,
  PRIMARY KEY ([idDetalle]),
  FOREIGN KEY ([idPedido]) REFERENCES [Pedido] ([idPedido]),
  FOREIGN KEY ([idModelo]) REFERENCES [Modelo] ([id])
);

CREATE TABLE [OrdenProduccion] (
  [idOrden] INT IDENTITY(1,1) NOT NULL,
  [idDetalle] INT NOT NULL,
  [idTurno] INT NOT NULL,
  [CantidadObjetivo] INT NOT NULL,
  [FechaCompromiso] DATE NOT NULL,
  [Estado] VARCHAR(20) NOT NULL CHECK ([Estado] IN ('Finalizado', 'En proceso', 'Cancelado')),
  [idUsuarioCreador] INT NOT NULL,
  [idLinea] INT NOT NULL,
  [lote] VARCHAR(255) NOT NULL,
  PRIMARY KEY ([idOrden]),
  FOREIGN KEY ([idDetalle]) REFERENCES [DetallePedido] ([idDetalle]),
  FOREIGN KEY ([idTurno]) REFERENCES [Turno] ([idTurno]),
  FOREIGN KEY ([idLinea]) REFERENCES [Linea] ([idLinea]),
  FOREIGN KEY ([idUsuarioCreador]) REFERENCES [Usuario] ([id])
);

CREATE TABLE [UsuarioRol] (
  [id] INT IDENTITY(1,1) NOT NULL,
  [idRol] INT NOT NULL,
  [idUsuario] INT NOT NULL,
  PRIMARY KEY ([id]),
  FOREIGN KEY ([idRol]) REFERENCES [Rol] ([id]),
  FOREIGN KEY ([idUsuario]) REFERENCES [Usuario] ([id])
);

CREATE TABLE [cajasAlmacen] (
  [id] INT IDENTITY(1,1) NOT NULL,
  [estatus] VARCHAR(20) NOT NULL CHECK ([estatus] IN ('Activa', 'Cerrada', 'Enviada')),
  [fechaInicio] DATETIME NOT NULL,
  [fechaCierre] DATETIME NOT NULL,
  [idUsuario] INT NOT NULL,
  PRIMARY KEY ([id]),
  FOREIGN KEY ([idUsuario]) REFERENCES [Usuario] ([id])
);

CREATE TABLE [Produccion] (
  [idProduccion] INT IDENTITY(1,1) NOT NULL,
  [idOrden] INT NOT NULL,
  [CantidadProducida] INT NOT NULL,
  [idUsuarioOperador] INT NOT NULL,
  [idTurno] INT NOT NULL,
  [idLinea] INT NOT NULL,
  [idValidador] INT NOT NULL,
  PRIMARY KEY ([idProduccion]),
  FOREIGN KEY ([idOrden]) REFERENCES [OrdenProduccion] ([idOrden]),
  FOREIGN KEY ([idUsuarioOperador]) REFERENCES [Usuario] ([id]),
  FOREIGN KEY ([idLinea]) REFERENCES [Linea] ([idLinea]),
  FOREIGN KEY ([idTurno]) REFERENCES [Turno] ([idTurno])
);

CREATE TABLE [Pieza] (
  [idPieza] INT IDENTITY(1,1) NOT NULL,
  [idOrden] INT NOT NULL,
  [idDetalle] INT NOT NULL,
  [idEstado] INT NOT NULL,
  [FechaCreacion] DATETIME NOT NULL,
  [numSerie] VARCHAR(255) NOT NULL UNIQUE,
  [idCajaAlmacen] INT NULL,
  PRIMARY KEY ([idPieza]),
  FOREIGN KEY ([idOrden]) REFERENCES [OrdenProduccion] ([idOrden]),
  FOREIGN KEY ([idDetalle]) REFERENCES [DetallePedido] ([idDetalle]),
  FOREIGN KEY ([idEstado]) REFERENCES [EstadoPieza] ([idEstado]),
  FOREIGN KEY ([idCajaAlmacen]) REFERENCES [cajasAlmacen] ([id])
);

CREATE TABLE [Ensamble] (
  [idEnsamble] INT IDENTITY(1,1) NOT NULL,
  [idProduccion] INT NOT NULL,
  [idPieza] INT NOT NULL,
  [FechaEnsamble] DATETIME NOT NULL,
  [Ensamblado] BIT NOT NULL,
  PRIMARY KEY ([idEnsamble]),
  FOREIGN KEY ([idPieza]) REFERENCES [Pieza] ([idPieza]),
  FOREIGN KEY ([idProduccion]) REFERENCES [Produccion] ([idProduccion])
);

CREATE TABLE [PruebaFuncional] (
  [idPrueba] INT IDENTITY(1,1) NOT NULL,
  [idPieza] INT NOT NULL,
  [idUsuario] INT NOT NULL,
  [encendido] BIT NOT NULL,
  [audio] BIT NOT NULL,
  [carga] BIT NOT NULL,
  [bluetooth] BIT NOT NULL,
  [resultado] VARCHAR(20) NOT NULL CHECK ([resultado] IN ('Aprobada', 'Fallida')),
  [FechaPrueba] DATETIME NOT NULL,
  PRIMARY KEY ([idPrueba]),
  FOREIGN KEY ([idPieza]) REFERENCES [Pieza] ([idPieza]),
  FOREIGN KEY ([idUsuario]) REFERENCES [Usuario] ([id])
);

CREATE TABLE [DetalleDefecto] (
  [id] INT IDENTITY(1,1) NOT NULL,
  [idPrueba] INT NOT NULL,
  [fallo] VARCHAR(255) NOT NULL,
  [descripcion] VARCHAR(255) NOT NULL,
  [retrabajo] BIT NOT NULL,
  [destino] VARCHAR(255) NOT NULL,
  [fechaRegistro] DATETIME NOT NULL,
  PRIMARY KEY ([id]),
  FOREIGN KEY ([idPrueba]) REFERENCES [PruebaFuncional] ([idPrueba])
);

CREATE TABLE [InspeccionCalidad] (
  [id] INT IDENTITY(1,1) NOT NULL,
  [idPieza] INT NOT NULL,
  [idUsuario] INT NOT NULL,
  [fechaInspeccion] DATETIME NOT NULL,
  [apariencia] VARCHAR(255) NOT NULL,
  [etiqueta] VARCHAR(255) NOT NULL,
  [accesorios] VARCHAR(255) NOT NULL,
  [observaciones] VARCHAR(MAX) NOT NULL,
  [resultado] VARCHAR(20) NOT NULL CHECK ([resultado] IN ('Aprobada', 'Fallida')),
  PRIMARY KEY ([id]),
  FOREIGN KEY ([idPieza]) REFERENCES [Pieza] ([idPieza]),
  FOREIGN KEY ([idUsuario]) REFERENCES [Usuario] ([id])
);

CREATE TABLE [HallazgoCalidad] (
  [id] INT IDENTITY(1,1) NOT NULL,
  [idInspeccion] INT NOT NULL,
  [causa] VARCHAR(255) NOT NULL,
  [tipo] VARCHAR(255) NOT NULL,
  [descripcion] VARCHAR(MAX) NOT NULL,
  [gravedad] VARCHAR(255) NOT NULL,
  [estatus] VARCHAR(255) NOT NULL,
  PRIMARY KEY ([id]),
  FOREIGN KEY ([idInspeccion]) REFERENCES [InspeccionCalidad] ([id])
);

CREATE TABLE [DisposicionPieza] (
  [id] INT IDENTITY(1,1) NOT NULL,
  [idPieza] INT NOT NULL,
  [origen] VARCHAR(255) NOT NULL,
  [destino] VARCHAR(255) NOT NULL,
  [comentario] VARCHAR(MAX) NULL,
  [fechaMovimiento] DATETIME NOT NULL,
  [idUsuario] INT NOT NULL,
  PRIMARY KEY ([id]),
  FOREIGN KEY ([idPieza]) REFERENCES [Pieza] ([idPieza]),
  FOREIGN KEY ([idUsuario]) REFERENCES [Usuario] ([id])
);

CREATE TABLE [cajaDetalle] (
  [id] INT IDENTITY(1,1) NOT NULL,
  [idCaja] INT NOT NULL,
  [idDetalle] INT NULL,
  PRIMARY KEY ([id]),
  FOREIGN KEY ([idCaja]) REFERENCES [cajasAlmacen] ([id]),
  FOREIGN KEY ([idDetalle]) REFERENCES [DetallePedido] ([idDetalle])
);

CREATE TABLE [DisposicionCaja] (
  [id] INT IDENTITY(1,1) NOT NULL,
  [idCaja] INT NOT NULL,
  [origen] VARCHAR(255) NOT NULL,
  [destino] VARCHAR(255) NOT NULL,
  [fechaMovimiento] DATETIME NOT NULL,
  [idUsuario] INT NOT NULL,
  PRIMARY KEY ([id]),
  FOREIGN KEY ([idCaja]) REFERENCES [cajasAlmacen] ([id]),
  FOREIGN KEY ([idUsuario]) REFERENCES [Usuario] ([id])
);

CREATE TABLE [Envio] (
  [id] INT IDENTITY(1,1) NOT NULL,
  [idCliente] INT NOT NULL,
  [estado] VARCHAR(20) NOT NULL CHECK ([estado] IN ('Pendiente', 'Enviado', 'Entregado')),
  [fechaEnvio] DATETIME NOT NULL,
  [fechaEntrega] DATETIME NOT NULL,
  [guia] VARCHAR(255) NOT NULL,
  PRIMARY KEY ([id]),
  FOREIGN KEY ([idCliente]) REFERENCES [Cliente] ([idCliente])
);

CREATE TABLE [Embarque] (
  [id] INT IDENTITY(1,1) NOT NULL,
  [idEnvio] INT NULL,
  [idCaja] INT NULL,
  [autorizado] BIT NULL,
  PRIMARY KEY ([id]),
  FOREIGN KEY ([idEnvio]) REFERENCES [Envio] ([id]),
  FOREIGN KEY ([idCaja]) REFERENCES [cajasAlmacen] ([id])
);

CREATE TABLE [ProduccionTurno] (
  [id] INT IDENTITY(1,1) NOT NULL,
  [idTurno] INT NOT NULL,
  [idLinea] INT NOT NULL,
  [idOrden] INT NOT NULL,
  [produccionObjetivo] INT NOT NULL,
  [produccionReal] INT NOT NULL,
  [fecha] DATE NOT NULL,
  PRIMARY KEY ([id]),
  FOREIGN KEY ([idTurno]) REFERENCES [Turno] ([idTurno]),
  FOREIGN KEY ([idLinea]) REFERENCES [Linea] ([idLinea]),
  FOREIGN KEY ([idOrden]) REFERENCES [OrdenProduccion] ([idOrden])
);

CREATE TABLE [ReporteTurno] (
  [id] INT IDENTITY(1,1) NOT NULL,
  [idProduccionTurno] INT NOT NULL,
  [ProduccionTotal] INT NOT NULL,
  [produccionObjetivo] INT NOT NULL,
  [variacion] INT NOT NULL,
  [aprobadas] INT NOT NULL,
  [retenidas] INT NOT NULL,
  [scrap] INT NOT NULL,
  [retrabajo] INT NOT NULL,
  [observaciones] VARCHAR(MAX) NOT NULL,
  [archivoGenerado] VARCHAR(255) NOT NULL,
  [fechaGeneracion] DATETIME NOT NULL,
  [idUsuario] INT NOT NULL,
  PRIMARY KEY ([id]),
  FOREIGN KEY ([idProduccionTurno]) REFERENCES [ProduccionTurno] ([id]),
  FOREIGN KEY ([idUsuario]) REFERENCES [Usuario] ([id])
);

CREATE TABLE [auditoriaCierre] (
  [id] INT IDENTITY(1,1) NOT NULL,
  [idReporte] INT NOT NULL,
  [idUsuario] INT NOT NULL,
  [accion] VARCHAR(20) NOT NULL CHECK ([accion] IN ('Corrección', 'Reapertura', 'Ajuste')),
  [descripcion] VARCHAR(MAX) NULL,
  [motivo] VARCHAR(MAX) NULL,
  [fechaAuditoria] DATETIME NOT NULL,
  PRIMARY KEY ([id]),
  FOREIGN KEY ([idReporte]) REFERENCES [ReporteTurno] ([id]),
  FOREIGN KEY ([idUsuario]) REFERENCES [Usuario] ([id])
);

CREATE TABLE [Auditoria] (
  [idAuditoria] INT IDENTITY(1,1) NOT NULL,
  [TablaAfectada] VARCHAR(255) NOT NULL,
  [registroId] INT NOT NULL,
  [Accion] VARCHAR(255) NOT NULL,
  [idUsuario] INT NOT NULL,
  [FechaAccion] DATETIME NOT NULL,
  [Motivo] VARCHAR(255) NOT NULL,
  [ValorAnterior] VARCHAR(255) NOT NULL,
  [ValorNuevo] VARCHAR(255) NOT NULL,
  [Categoria] VARCHAR(255) NULL,
  PRIMARY KEY ([idAuditoria]),
  FOREIGN KEY ([idUsuario]) REFERENCES [Usuario] ([id])
);

USE [nova_sound];
SELECT TABLE_NAME 
FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_TYPE = 'BASE TABLE'
ORDER BY TABLE_NAME;

