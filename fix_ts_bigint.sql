-- SQL для исправления типа колонки ts на BIGINT
-- Выполнить на сервере через psql

ALTER TABLE prices ALTER COLUMN ts TYPE BIGINT;



