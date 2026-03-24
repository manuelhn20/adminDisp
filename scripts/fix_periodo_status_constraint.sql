-- Fix: Allow periodo status values 0 (Inactivo), 1 (Activo), 2 (Cerrado)
-- Session: 2026-03-24 14:39:20 - Update status model to support 3 states
-- Error: CHECK constraint "chkPeriodoStatus" conflicted when trying to set status=2

USE kardex;
GO

-- Drop old constraint if exists
IF OBJECT_ID('dbo.chkPeriodoStatus', 'C') IS NOT NULL
BEGIN
    ALTER TABLE dbo.periodo DROP CONSTRAINT chkPeriodoStatus;
END

IF OBJECT_ID('dbo.chkPeriodoEstado', 'C') IS NOT NULL
BEGIN
    ALTER TABLE dbo.periodo DROP CONSTRAINT chkPeriodoEstado;
END

-- Add new constraint allowing 0, 1, 2
ALTER TABLE dbo.periodo
ADD CONSTRAINT chkPeriodoStatus CHECK (status IN (0, 1, 2));

PRINT 'Constraint fixed: chkPeriodoStatus now allows status 0 (Inactivo), 1 (Activo), 2 (Cerrado)';
