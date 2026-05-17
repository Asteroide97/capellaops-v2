MERGE INTO planes AS target
USING (
    VALUES
        ('basico', 'Básico', 'Inventario para operación esencial.', '["inventory"]'),
        ('pro', 'Pro', 'Inventario, POS y facturación marcada como pendiente.', '["inventory","pos","billing_pending"]'),
        ('total', 'Total', 'Inventario, POS, CRM y gestión de proyectos.', '["inventory","pos","billing_pending","crm","pm"]')
) AS source (code, name, description, modules)
ON target.code = source.code
WHEN MATCHED THEN
    UPDATE SET
        name = source.name,
        description = source.description,
        modules = source.modules
WHEN NOT MATCHED THEN
    INSERT (code, name, description, modules)
    VALUES (source.code, source.name, source.description, source.modules);
