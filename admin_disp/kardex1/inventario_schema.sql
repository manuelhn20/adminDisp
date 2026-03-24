-- ============================================================
-- MÓDULO INVENTARIO - Schema de Base de Datos
-- ============================================================

-- ------------------------------------------------------------
-- TABLA: marca
-- Soft delete: estado 1=activo, 0=inactivo
-- No se usa DELETE físico para evitar problemas de cascada
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS marca (
  id        INT AUTO_INCREMENT PRIMARY KEY,
  nombre    VARCHAR(100) NOT NULL,
  estado    TINYINT(1)   NOT NULL DEFAULT 1,
  createdAt DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updatedAt DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- TABLA: producto
-- upc1 y upc2: únicos globalmente entre ambas columnas
-- Unicidad cruzada se valida en capa de aplicación y triggers
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS producto (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  nombre      VARCHAR(150) NOT NULL,
  descripcion TEXT,
  upc1        VARCHAR(50)  DEFAULT NULL,
  upc2        VARCHAR(50)  DEFAULT NULL,
  marcaId     INT          DEFAULT NULL,
  precio      DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  estado      TINYINT(1)   NOT NULL DEFAULT 1,
  createdAt   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updatedAt   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT uq_producto_upc1 UNIQUE (upc1),
  CONSTRAINT uq_producto_upc2 UNIQUE (upc2),
  CONSTRAINT fk_producto_marca FOREIGN KEY (marcaId)
    REFERENCES marca(id)
    -- Sin ON DELETE CASCADE: marca usa soft delete, nunca se elimina físicamente
);

-- Trigger: garantiza unicidad global entre upc1 y upc2 en INSERT
DELIMITER $$
CREATE TRIGGER trg_producto_upc_insert
BEFORE INSERT ON producto
FOR EACH ROW
BEGIN
  -- upc1 no puede existir en upc2 de ningún otro producto
  IF NEW.upc1 IS NOT NULL AND EXISTS (
    SELECT 1 FROM producto WHERE upc2 = NEW.upc1
  ) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'UPC1 ya existe como UPC2 en otro producto';
  END IF;
  -- upc2 no puede existir en upc1 de ningún otro producto
  IF NEW.upc2 IS NOT NULL AND EXISTS (
    SELECT 1 FROM producto WHERE upc1 = NEW.upc2
  ) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'UPC2 ya existe como UPC1 en otro producto';
  END IF;
END$$
DELIMITER ;

-- Trigger: garantiza unicidad global entre upc1 y upc2 en UPDATE
DELIMITER $$
CREATE TRIGGER trg_producto_upc_update
BEFORE UPDATE ON producto
FOR EACH ROW
BEGIN
  IF NEW.upc1 IS NOT NULL AND EXISTS (
    SELECT 1 FROM producto WHERE upc2 = NEW.upc1 AND id != NEW.id
  ) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'UPC1 ya existe como UPC2 en otro producto';
  END IF;
  IF NEW.upc2 IS NOT NULL AND EXISTS (
    SELECT 1 FROM producto WHERE upc1 = NEW.upc2 AND id != NEW.id
  ) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'UPC2 ya existe como UPC1 en otro producto';
  END IF;
END$$
DELIMITER ;

-- ------------------------------------------------------------
-- TABLA: movimientoResumen
-- tipo: 'entrada' | 'salida' | 'ajuste'
-- estado: 1=activo, 0=borrado lógico (no cuenta en inventario)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS movimientoResumen (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  tipo        ENUM('entrada','salida','ajuste') NOT NULL,
  fecha       DATE         NOT NULL,
  referencia  VARCHAR(100) DEFAULT NULL,
  observacion TEXT         DEFAULT NULL,
  estado      TINYINT(1)   NOT NULL DEFAULT 1,
  createdAt   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updatedAt   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- TABLA: movimientoDetalle
-- estado: 1=activo, 0=borrado lógico (hereda del resumen)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS movimientoDetalle (
  id                  INT AUTO_INCREMENT PRIMARY KEY,
  movimientoResumenId INT            NOT NULL,
  productoId          INT            NOT NULL,
  cantidad            DECIMAL(10,2)  NOT NULL,
  precio              DECIMAL(10,2)  NOT NULL DEFAULT 0.00,
  estado              TINYINT(1)     NOT NULL DEFAULT 1,
  createdAt           DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_detalle_resumen  FOREIGN KEY (movimientoResumenId)
    REFERENCES movimientoResumen(id),
  CONSTRAINT fk_detalle_producto FOREIGN KEY (productoId)
    REFERENCES producto(id)
);

-- ------------------------------------------------------------
-- VISTA: stock actual por producto
-- Solo considera movimientos con estado=1
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW vw_stock AS
SELECT
  p.id          AS productoId,
  p.nombre      AS producto,
  p.upc1,
  p.upc2,
  COALESCE(SUM(
    CASE
      WHEN r.tipo IN ('entrada', 'ajuste') THEN d.cantidad
      WHEN r.tipo = 'salida'              THEN -d.cantidad
      ELSE 0
    END
  ), 0) AS stock
FROM producto p
LEFT JOIN movimientoDetalle  d ON d.productoId          = p.id    AND d.estado = 1
LEFT JOIN movimientoResumen  r ON r.id                  = d.movimientoResumenId AND r.estado = 1
WHERE p.estado = 1
GROUP BY p.id, p.nombre, p.upc1, p.upc2;
