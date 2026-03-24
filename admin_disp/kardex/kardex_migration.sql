-- =============================================================================
-- KARDEX — Migration script
-- Base de datos: kardex
-- Ejecutar una sola vez sobre la BD kardex (no sobre ProimaDB / admin_disp).
-- =============================================================================

USE kardex;
GO

-- =============================================================================
-- 1. periodo
--    Reemplaza la tabla Ajustes (2 filas) y la tabla Configuracion.
--    Solo puede existir UN registro con estado = 'A' a la vez.
-- =============================================================================
IF OBJECT_ID('dbo.periodo', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.periodo (
        id          INT IDENTITY(1,1) PRIMARY KEY,
        nombre      NVARCHAR(100) NOT NULL,
        mes         TINYINT       NOT NULL,
        ano         SMALLINT      NOT NULL,
        fechaInicio DATE          NOT NULL,
        fechaFin    DATE          NOT NULL,
        estado      CHAR(1)       NOT NULL DEFAULT 'I',
        createdAt   DATETIME      NOT NULL DEFAULT GETDATE(),
        CONSTRAINT chkPeriodoEstado CHECK (estado IN ('A', 'I')),
        CONSTRAINT chkPeriodoMes    CHECK (mes BETWEEN 1 AND 12)
    );

    -- Garantiza que solo exista 1 fila activa en todo momento.
    CREATE UNIQUE INDEX uxPeriodoActivo
        ON dbo.periodo(estado)
        WHERE estado = 'A';

    PRINT 'Tabla periodo creada.';
END
ELSE
    PRINT 'Tabla periodo ya existe — omitida.';
GO

-- =============================================================================
-- 2. marca
--    ID viene del ERPNext (string). Se sincroniza desde SharePoint.
-- =============================================================================
IF OBJECT_ID('dbo.marca', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.marca (
        id          NVARCHAR(50)  NOT NULL PRIMARY KEY,
        descripcion NVARCHAR(100) NOT NULL,
        syncedAt    DATETIME      NOT NULL DEFAULT GETDATE()
    );

    PRINT 'Tabla marca creada.';
END
ELSE
    PRINT 'Tabla marca ya existe — omitida.';
GO

-- =============================================================================
-- 3. producto
--    Campos del reporte: ID, itemName, brand (FK marca), categoria,
--    um (Default Unit of Measure), ms (Maintain Stock + NOT Disabled).
-- =============================================================================
IF OBJECT_ID('dbo.producto', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.producto (
        id          NVARCHAR(50)  NOT NULL PRIMARY KEY,
        itemName    NVARCHAR(200) NOT NULL,
        brand       NVARCHAR(50)  NULL REFERENCES dbo.marca(id),
        categoria   NVARCHAR(100) NULL,
        um          NVARCHAR(20)  NULL,
        ms          BIT           NOT NULL DEFAULT 1,
        syncedAt    DATETIME      NOT NULL DEFAULT GETDATE()
    );

    CREATE INDEX ixProductoBrand    ON dbo.producto(brand);
    CREATE INDEX ixProductoCategoria ON dbo.producto(categoria);

    PRINT 'Tabla producto creada.';
END
ELSE
    PRINT 'Tabla producto ya existe — omitida.';
GO

-- =============================================================================
-- 4. almacen
--    Campos del reporte: ID, status (Is Group Warehouse),
--    company, descripcion (Parent Warehouse).
--    status = 0 → almacén real; status = 1 → grupo (se filtra en app).
-- =============================================================================
IF OBJECT_ID('dbo.almacen', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.almacen (
        id          NVARCHAR(50)  NOT NULL PRIMARY KEY,
        status      BIT           NOT NULL DEFAULT 0,
        company     NVARCHAR(100) NULL,
        descripcion NVARCHAR(150) NULL,
        tipoAlmacen NVARCHAR(100) NULL,
        syncedAt    DATETIME      NOT NULL DEFAULT GETDATE()
    );

    PRINT 'Tabla almacen creada.';
END
ELSE
BEGIN
    -- Agregar columna tipoAlmacen si no existe
    IF COL_LENGTH('dbo.almacen', 'tipoAlmacen') IS NULL
    BEGIN
        ALTER TABLE dbo.almacen ADD tipoAlmacen NVARCHAR(100) NULL;
        PRINT 'Columna tipoAlmacen agregada a tabla almacen.';
    END
    ELSE
        PRINT 'Tabla almacen ya existe — omitida.';
END
GO

-- =============================================================================
-- Verificación final
-- =============================================================================
SELECT
    TABLE_NAME          AS tabla,
    TABLE_TYPE          AS tipo
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = 'dbo'
  AND TABLE_NAME IN ('periodo', 'marca', 'producto', 'almacen')
ORDER BY TABLE_NAME;
GO

PRINT '=== Migration KARDEX completada ===';
GO
