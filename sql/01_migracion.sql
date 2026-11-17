/* Cambios mínimos al esquema original para que el backend funcione.
   Ejecutar UNA vez sobre la BD nova_sound, después de nova_sound.sql.

   1) Usuario.Nombre: el formulario de registro pide "Nombre / ID Operador" y
      el correo; la tabla solo tenía Usuario + Contrasena. Se guarda el correo
      en Usuario.Usuario (es el que se usa para iniciar sesión) y el nombre aquí.
*/
USE [nova_sound];
GO

IF COL_LENGTH('Usuario', 'Nombre') IS NULL
    ALTER TABLE [Usuario] ADD [Nombre] VARCHAR(255) NULL;
GO

/* 2) Índices que el backend usa para buscar (opcionales pero recomendados). */
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_Usuario_Usuario')
    CREATE UNIQUE INDEX UX_Usuario_Usuario ON [Usuario]([Usuario]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_OrdenProduccion_lote')
    CREATE INDEX IX_OrdenProduccion_lote ON [OrdenProduccion]([lote]);
GO
