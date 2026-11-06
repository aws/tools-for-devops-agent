# Table Health Assessment Queries

Run as superuser or admin. All queries are read-only.

## 1. Table Design Overview

Distribution, sort keys, compression, skew for top 100 tables by size.

```sql
SELECT "schema",
       "table",
       tbl_rows,
       diststyle,
       sortkey1,
       sortkey_num,
       skew_rows,
       skew_sortkey1,
       stats_off,
       unsorted,
       max_varchar,
       encoded,
       size AS size_mb,
       pct_used
FROM svv_table_info
WHERE "schema" NOT IN ('pg_catalog', 'information_schema', 'pg_internal')
ORDER BY size DESC
LIMIT 100;
```

## 2. Tables with High Skew (>= 4)

```sql
SELECT "schema", "table", tbl_rows, diststyle, skew_rows
FROM svv_table_info
WHERE skew_rows >= 4
  AND "schema" NOT IN ('pg_catalog', 'information_schema', 'pg_internal')
ORDER BY skew_rows DESC;
```

## 3. Tables with Stale Statistics (stats_off > 10%)

```sql
SELECT "schema", "table", tbl_rows, stats_off
FROM svv_table_info
WHERE stats_off > 10
  AND "schema" NOT IN ('pg_catalog', 'information_schema', 'pg_internal')
ORDER BY stats_off DESC;
```

## 4. Tables with High Unsorted Data (> 20%)

```sql
SELECT "schema", "table", tbl_rows, unsorted, sortkey1
FROM svv_table_info
WHERE unsorted > 20
  AND "schema" NOT IN ('pg_catalog', 'information_schema', 'pg_internal')
ORDER BY unsorted DESC;
```

## 5. Tables with Deletion Bloat (> 10% rows pending VACUUM DELETE)

```sql
-- SVV_TABLE_INFO.empty is documented by AWS as "for internal use... no
-- longer used" and does not reliably reflect deleted-row percentage.
-- Derive it instead from tbl_rows (includes rows marked for deletion but
-- not yet vacuumed) vs. estimated_visible_rows (excludes them).
SELECT "schema",
       "table",
       tbl_rows,
       estimated_visible_rows,
       pct_deleted
FROM (
    SELECT "schema",
           "table",
           tbl_rows,
           estimated_visible_rows,
           ROUND(100.0 * (tbl_rows - estimated_visible_rows) / NULLIF(tbl_rows, 0), 1) AS pct_deleted
    FROM svv_table_info
    WHERE tbl_rows > 0
      AND "schema" NOT IN ('pg_catalog', 'information_schema', 'pg_internal')
) t
WHERE pct_deleted > 10
ORDER BY pct_deleted DESC;
```

## 6. Large Tables without Sort Keys

```sql
SELECT "schema", "table", tbl_rows, size AS size_mb, diststyle
FROM svv_table_info
WHERE sortkey1 IS NULL
  AND tbl_rows > 1000000
  AND "schema" NOT IN ('pg_catalog', 'information_schema', 'pg_internal')
ORDER BY size DESC;
```

## 7. Tables without Compression

```sql
SELECT "schema", "table", tbl_rows, size AS size_mb, encoded
FROM svv_table_info
WHERE encoded = 'N'
  AND tbl_rows > 100000
  AND "schema" NOT IN ('pg_catalog', 'information_schema', 'pg_internal')
ORDER BY size DESC;
```

## 8. Wide VARCHAR Columns (> 1000)

```sql
SELECT "schema", "table", max_varchar, tbl_rows, size AS size_mb
FROM svv_table_info
WHERE max_varchar > 1000
  AND "schema" NOT IN ('pg_catalog', 'information_schema', 'pg_internal')
ORDER BY max_varchar DESC;
```
