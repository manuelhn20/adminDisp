SET XACT_ABORT ON;
BEGIN TRY
    BEGIN TRANSACTION;

    ------------------------------------------------------------
    -- 0. Limpieza previa
    ------------------------------------------------------------
    IF OBJECT_ID('tempdb..#MapeoDispositivos') IS NOT NULL
        DROP TABLE #MapeoDispositivos;

    IF OBJECT_ID('admin_disp.dbo.dispositivo_nuevo', 'U') IS NOT NULL
        DROP TABLE admin_disp.dbo.dispositivo_nuevo;

    ------------------------------------------------------------
    -- 1. Eliminar asignaciones ligadas a dispositivos a borrar
    ------------------------------------------------------------
    DELETE FROM admin_disp.dbo.asignacion
    WHERE fk_id_dispositivo BETWEEN 5029 AND 5078;

    ------------------------------------------------------------
    -- 2. Eliminar dispositivos del 5029 al 5078
    ------------------------------------------------------------
    DELETE FROM admin_disp.dbo.dispositivo
    WHERE id_dispositivo BETWEEN 5029 AND 5078;

    ------------------------------------------------------------
    -- 3. Crear mapeo: id viejo -> id nuevo
    --    Solo para los dispositivos desde 5113 en adelante
    ------------------------------------------------------------
    SELECT
        d.id_dispositivo AS id_viejo,
        ROW_NUMBER() OVER (ORDER BY d.id_dispositivo) AS id_nuevo
    INTO #MapeoDispositivos
    FROM admin_disp.dbo.dispositivo d
    WHERE d.id_dispositivo >= 5113;

    ------------------------------------------------------------
    -- 4. Crear tabla auxiliar vacía con la misma estructura
    ------------------------------------------------------------
    SELECT TOP 0
        id_dispositivo,
        numero_serie,
        imei,
        imei2,
        direccion_mac,
        ip_asignada,
        tamano,
        color,
        cargador,
        estado,
        fk_id_modelo,
        observaciones,
        fecha_obt,
        extension,
        fk_id_plan,
        fk_id_historico_planes,
        identificador
    INTO admin_disp.dbo.dispositivo_nuevo
    FROM admin_disp.dbo.dispositivo;

    ------------------------------------------------------------
    -- 5. Insertar registros renumerados en la tabla auxiliar
    --    OJO: esta tabla también heredó IDENTITY, por eso se activa
    ------------------------------------------------------------
    SET IDENTITY_INSERT admin_disp.dbo.dispositivo_nuevo ON;

    INSERT INTO admin_disp.dbo.dispositivo_nuevo (
        id_dispositivo,
        numero_serie,
        imei,
        imei2,
        direccion_mac,
        ip_asignada,
        tamano,
        color,
        cargador,
        estado,
        fk_id_modelo,
        observaciones,
        fecha_obt,
        extension,
        fk_id_plan,
        fk_id_historico_planes,
        identificador
    )
    SELECT
        m.id_nuevo,
        d.numero_serie,
        d.imei,
        d.imei2,
        d.direccion_mac,
        d.ip_asignada,
        d.tamano,
        d.color,
        d.cargador,
        d.estado,
        d.fk_id_modelo,
        d.observaciones,
        d.fecha_obt,
        d.extension,
        d.fk_id_plan,
        d.fk_id_historico_planes,
        d.identificador
    FROM admin_disp.dbo.dispositivo d
    INNER JOIN #MapeoDispositivos m
        ON d.id_dispositivo = m.id_viejo;

    SET IDENTITY_INSERT admin_disp.dbo.dispositivo_nuevo OFF;

    ------------------------------------------------------------
    -- 6. Actualizar asignaciones con el nuevo id
    ------------------------------------------------------------
    UPDATE a
    SET a.fk_id_dispositivo = m.id_nuevo
    FROM admin_disp.dbo.asignacion a
    INNER JOIN #MapeoDispositivos m
        ON a.fk_id_dispositivo = m.id_viejo;

    ------------------------------------------------------------
    -- 7. Desactivar constraints en asignacion
    ------------------------------------------------------------
    ALTER TABLE admin_disp.dbo.asignacion NOCHECK CONSTRAINT ALL;

    ------------------------------------------------------------
    -- 8. Vaciar tabla original
    ------------------------------------------------------------
    DELETE FROM admin_disp.dbo.dispositivo;

    ------------------------------------------------------------
    -- 9. Insertar datos renumerados en tabla original
    ------------------------------------------------------------
    SET IDENTITY_INSERT admin_disp.dbo.dispositivo ON;

    INSERT INTO admin_disp.dbo.dispositivo (
        id_dispositivo,
        numero_serie,
        imei,
        imei2,
        direccion_mac,
        ip_asignada,
        tamano,
        color,
        cargador,
        estado,
        fk_id_modelo,
        observaciones,
        fecha_obt,
        extension,
        fk_id_plan,
        fk_id_historico_planes,
        identificador
    )
    SELECT
        id_dispositivo,
        numero_serie,
        imei,
        imei2,
        direccion_mac,
        ip_asignada,
        tamano,
        color,
        cargador,
        estado,
        fk_id_modelo,
        observaciones,
        fecha_obt,
        extension,
        fk_id_plan,
        fk_id_historico_planes,
        identificador
    FROM admin_disp.dbo.dispositivo_nuevo
    ORDER BY id_dispositivo;

    SET IDENTITY_INSERT admin_disp.dbo.dispositivo OFF;

    ------------------------------------------------------------
    -- 10. Reactivar constraints
    ------------------------------------------------------------
    ALTER TABLE admin_disp.dbo.asignacion WITH CHECK CHECK CONSTRAINT ALL;

    ------------------------------------------------------------
    -- 11. Reseed para que el próximo ID siga correctamente
    ------------------------------------------------------------
    DECLARE @MaxID INT;
    SELECT @MaxID = ISNULL(MAX(id_dispositivo), 0)
    FROM admin_disp.dbo.dispositivo;

    DBCC CHECKIDENT ('admin_disp.dbo.dispositivo', RESEED, @MaxID);

    ------------------------------------------------------------
    -- 12. Limpieza
    ------------------------------------------------------------
    DROP TABLE #MapeoDispositivos;
    DROP TABLE admin_disp.dbo.dispositivo_nuevo;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;

    IF OBJECT_ID('tempdb..#MapeoDispositivos') IS NOT NULL
        DROP TABLE #MapeoDispositivos;

    IF OBJECT_ID('admin_disp.dbo.dispositivo_nuevo', 'U') IS NOT NULL
        DROP TABLE admin_disp.dbo.dispositivo_nuevo;

    THROW;
END CATCH;
