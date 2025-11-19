"""
Dataset routes for uploading, listing, viewing, and aggregating CSV data.
"""

import csv
import io
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

from src.database import get_db, get_db_with_tenant
from src.models import Dataset, DatasetRow, Tenant
from src.auth import get_current_user
from src.config import MAX_FILE_SIZE_BYTES

router = APIRouter(prefix="/datasets", tags=["Datasets"])


# ============================================
# Request/Response Schemas
# ============================================

class ColumnInfo(BaseModel):
    name: str
    type: str  # "categorical" or "continuous"


class DatasetMetadata(BaseModel):
    id: str
    name: str
    columns: list[ColumnInfo]
    row_count: int
    created_at: str


class DatasetDetail(BaseModel):
    id: str
    name: str
    columns: list[ColumnInfo]
    row_count: int
    created_at: str
    data: list[dict]


class FilterCondition(BaseModel):
    column: str
    value: str


class AggregateRequest(BaseModel):
    group_by: str  # Column name to group by (categorical)
    metrics: list[str]  # Column names to aggregate (continuous)
    filters: list[FilterCondition] = []  # Optional filters to apply before aggregating


class AggregateResult(BaseModel):
    group_value: str
    aggregations: dict  # {column_name: {min, max, avg}}


class AggregateResponse(BaseModel):
    group_by: str
    results: list[AggregateResult]


# ============================================
# Helper Functions
# ============================================

def detect_column_type(values: list) -> str:
    """
    Detect if a column is categorical or continuous based on its values.

    Rules:
    - If <90% of values are numeric -> categorical
    - If numeric but high uniqueness + integers -> categorical (likely ID/year)
    - Otherwise -> continuous
    """
    non_null = [v for v in values if v is not None and str(v).strip() != ""]

    if not non_null:
        return "categorical"

    # Count how many values are numeric
    numeric_values = []
    for v in non_null:
        try:
            numeric_values.append(float(v))
        except (ValueError, TypeError):
            pass

    # If less than 90% numeric, it's categorical
    if len(numeric_values) / len(non_null) < 0.9:
        return "categorical"

    # Check column characteristics
    unique_ratio = len(set(numeric_values)) / len(numeric_values)
    all_integers = all(v == int(v) for v in numeric_values)
    max_value = max(numeric_values)
    min_value = min(numeric_values)

    # Year detection: integers in typical year range (1900-2100)
    # Years should always be categorical for grouping purposes
    if all_integers and 1900 <= min_value and max_value <= 2100:
        return "categorical"

    # High uniqueness small integers are likely IDs
    # Large numbers (like population in millions) should be continuous
    if unique_ratio > 0.9 and all_integers and max_value < 10000:
        return "categorical"

    return "continuous"


def parse_csv_value(value: str, col_type: str):
    """
    Parse a CSV value based on its detected type.
    Converts numeric strings to floats for continuous columns.
    """
    if value is None or str(value).strip() == "":
        return None

    value = str(value).strip()

    if col_type == "continuous":
        try:
            return float(value)
        except ValueError:
            return None
    else:
        return value


def validate_csv(content: str) -> tuple[list[dict], list[ColumnInfo], list[str]]:
    """
    Validate and parse CSV content.

    Returns:
        - List of row dicts
        - List of column info
        - List of error messages (empty if valid)
    """
    errors = []

    try:
        # Parse CSV
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)

        if not rows:
            errors.append("CSV file is empty or has no data rows")
            return [], [], errors

        # Get column names
        columns = reader.fieldnames
        if not columns:
            errors.append("CSV file has no headers")
            return [], [], errors

        # Check for duplicate column names
        if len(columns) != len(set(columns)):
            duplicates = [c for c in columns if columns.count(c) > 1]
            errors.append(f"Duplicate column names found: {set(duplicates)}")
            return [], [], errors

        # Detect column types
        column_info = []
        for col_name in columns:
            col_values = [row.get(col_name) for row in rows]
            col_type = detect_column_type(col_values)
            column_info.append(ColumnInfo(name=col_name, type=col_type))

        # Parse values according to type
        parsed_rows = []
        for row_idx, row in enumerate(rows):
            parsed_row = {}
            for col_info in column_info:
                raw_value = row.get(col_info.name)
                parsed_value = parse_csv_value(raw_value, col_info.type)
                parsed_row[col_info.name] = parsed_value
            parsed_rows.append(parsed_row)

        return parsed_rows, column_info, errors

    except csv.Error as e:
        errors.append(f"CSV parsing error: {str(e)}")
        return [], [], errors
    except Exception as e:
        errors.append(f"Unexpected error parsing CSV: {str(e)}")
        return [], [], errors


# ============================================
# Routes
# ============================================

@router.get("", response_model=list[DatasetMetadata])
async def list_datasets(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all datasets for the current user's tenant.
    Uses both WHERE clause and RLS for defense in depth.
    """
    tenant_id = current_user["tenant_id"]

    # Set RLS context
    db.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))

    # Query with explicit WHERE clause (defense in depth)
    datasets = db.query(Dataset).filter(
        Dataset.tenant_id == tenant_id
    ).order_by(Dataset.created_at.desc()).all()

    return [
        DatasetMetadata(
            id=str(d.id),
            name=d.name,
            columns=[ColumnInfo(**c) for c in d.columns],
            row_count=d.row_count,
            created_at=d.created_at.isoformat()
        )
        for d in datasets
    ]


@router.post("", response_model=DatasetMetadata)
async def upload_dataset(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload a CSV file as a new dataset.
    Validates file size, parses CSV, and stores data.
    """
    tenant_id = current_user["tenant_id"]
    user_id = current_user["user_id"]

    # Check file extension
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file"
        )

    # Read file content
    content = await file.read()

    # Check file size
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024*1024)}MB"
        )

    # Decode content
    try:
        content_str = content.decode('utf-8')
    except UnicodeDecodeError:
        try:
            content_str = content.decode('latin-1')
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to decode file. Please ensure it's a valid CSV with UTF-8 or Latin-1 encoding."
            )

    # Parse and validate CSV
    parsed_rows, column_info, errors = validate_csv(content_str)

    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV validation failed: {'; '.join(errors)}"
        )

    # Set RLS context
    db.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))

    # Create dataset record
    dataset = Dataset(
        tenant_id=tenant_id,
        user_id=user_id,
        name=file.filename,
        columns=[c.model_dump() for c in column_info],
        row_count=len(parsed_rows)
    )
    db.add(dataset)
    db.flush()  # Get the dataset ID

    # Create dataset rows
    for row_data in parsed_rows:
        row = DatasetRow(
            dataset_id=dataset.id,
            tenant_id=tenant_id,
            row_data=row_data
        )
        db.add(row)

    db.commit()
    db.refresh(dataset)

    return DatasetMetadata(
        id=str(dataset.id),
        name=dataset.name,
        columns=[ColumnInfo(**c) for c in dataset.columns],
        row_count=dataset.row_count,
        created_at=dataset.created_at.isoformat()
    )


@router.get("/{dataset_id}", response_model=DatasetDetail)
async def get_dataset(
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get full dataset with all rows.
    Uses both WHERE clause and RLS for defense in depth.
    """
    tenant_id = current_user["tenant_id"]

    # Set RLS context
    db.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))

    # Query with explicit WHERE clause
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.tenant_id == tenant_id
    ).first()

    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )

    # Get all rows
    rows = db.query(DatasetRow).filter(
        DatasetRow.dataset_id == dataset_id,
        DatasetRow.tenant_id == tenant_id
    ).all()

    return DatasetDetail(
        id=str(dataset.id),
        name=dataset.name,
        columns=[ColumnInfo(**c) for c in dataset.columns],
        row_count=dataset.row_count,
        created_at=dataset.created_at.isoformat(),
        data=[row.row_data for row in rows]
    )


@router.post("/{dataset_id}/aggregate", response_model=AggregateResponse)
async def aggregate_dataset(
    dataset_id: str,
    request: AggregateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Perform aggregation on dataset.
    Groups by categorical column and calculates min/max/avg for continuous columns.
    """
    tenant_id = current_user["tenant_id"]

    # Set RLS context
    db.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))

    # Get dataset to validate columns
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.tenant_id == tenant_id
    ).first()

    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )

    # Validate group_by column exists and is categorical
    column_map = {c["name"]: c["type"] for c in dataset.columns}

    if request.group_by not in column_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Column '{request.group_by}' not found in dataset"
        )

    if column_map[request.group_by] != "categorical":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Column '{request.group_by}' is not categorical and cannot be used for grouping"
        )

    # Validate metric columns exist and are continuous
    for metric in request.metrics:
        if metric not in column_map:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Column '{metric}' not found in dataset"
            )
        if column_map[metric] != "continuous":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Column '{metric}' is not continuous and cannot be aggregated"
            )

    # Validate filter columns exist
    for f in request.filters:
        if f.column not in column_map:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Filter column '{f.column}' not found in dataset"
            )

    # Build aggregation query using Postgres JSONB operators
    # This runs efficiently in the database
    # Note: Column aliases must be quoted to preserve case (e.g., lifeExp_min not lifeexp_min)
    metric_selects = []
    for metric in request.metrics:
        metric_selects.extend([
            f"MIN((row_data->>'{metric}')::numeric) as \"{metric}_min\"",
            f"MAX((row_data->>'{metric}')::numeric) as \"{metric}_max\"",
            f"AVG((row_data->>'{metric}')::numeric) as \"{metric}_avg\""
        ])

    # Build filter conditions
    filter_conditions = []
    query_params = {"dataset_id": dataset_id, "tenant_id": tenant_id}
    for i, f in enumerate(request.filters):
        param_name = f"filter_{i}"
        filter_conditions.append(f"row_data->>'{f.column}' = :{param_name}")
        query_params[param_name] = f.value

    # Build WHERE clause
    where_clause = "WHERE dataset_id = :dataset_id AND tenant_id = :tenant_id"
    if filter_conditions:
        where_clause += " AND " + " AND ".join(filter_conditions)

    query = f"""
        SELECT
            row_data->>'{request.group_by}' as group_value,
            {', '.join(metric_selects)}
        FROM dataset_rows
        {where_clause}
        GROUP BY row_data->>'{request.group_by}'
        ORDER BY group_value
    """

    result = db.execute(text(query), query_params)

    # Format results
    results = []
    for row in result:
        aggregations = {}
        for metric in request.metrics:
            aggregations[metric] = {
                "min": float(getattr(row, f"{metric}_min")) if getattr(row, f"{metric}_min") is not None else None,
                "max": float(getattr(row, f"{metric}_max")) if getattr(row, f"{metric}_max") is not None else None,
                "avg": float(getattr(row, f"{metric}_avg")) if getattr(row, f"{metric}_avg") is not None else None
            }
        results.append(AggregateResult(
            group_value=str(row.group_value) if row.group_value else "N/A",
            aggregations=aggregations
        ))

    return AggregateResponse(
        group_by=request.group_by,
        results=results
    )


@router.delete("/{dataset_id}")
async def delete_dataset(
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a dataset and all its rows.
    """
    tenant_id = current_user["tenant_id"]

    # Set RLS context
    db.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))

    # Find and delete dataset
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.tenant_id == tenant_id
    ).first()

    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )

    db.delete(dataset)  # Cascade will delete rows
    db.commit()

    return {"message": "Dataset deleted successfully"}
