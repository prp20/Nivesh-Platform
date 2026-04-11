import asyncio
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from .. import analytics, crud, schemas, security

router = APIRouter(prefix="/funds", tags=["funds"])

@router.post("/", response_model=schemas.FundMasterRead, status_code=status.HTTP_201_CREATED)
async def create_fund(
    fund: schemas.FundMasterCreate, 
    session: AsyncSession = Depends(get_db),
    current_user: str = Depends(security.get_current_user)
):
    """Create a new fund entry (Requires Auth)."""
    existing = await crud.get_fund_master_by_code(session, fund.scheme_code)
    if existing:
        raise HTTPException(status_code=400, detail=f"Fund with scheme_code {fund.scheme_code} already exists")
    return await crud.create_fund_master(session, fund)

@router.get("/", response_model=schemas.FundMasterListResponse)
async def list_funds(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    category: Optional[str] = Query(None, description="Filter by scheme category"),
    subcategory: Optional[str] = Query(None, description="Filter by scheme subcategory"),
    amc: Optional[str] = Query(None, description="Filter by AMC name"),
    plan_type: Optional[str] = Query(None, description="Filter by plan type (Direct/Regular)"),
    benchmark_code: Optional[str] = Query(None, description="Filter by benchmark index code"),
    q: Optional[str] = Query(None, description="Search by fund name or code"),
    order_by: Optional[str] = Query("scheme_name", description="Sort field (scheme_name, -scheme_name)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
    current_user: str = Depends(security.get_current_user),
):
    """List all mutual funds with pagination and filtering."""
    total = await crud.get_fund_masters_count(
        session, is_active=is_active, category=category, subcategory=subcategory, amc=amc, plan_type=plan_type, benchmark_code=benchmark_code, search=q
    )
    items = await crud.get_all_fund_masters(
        session, is_active=is_active, category=category, subcategory=subcategory, amc=amc, plan_type=plan_type, benchmark_code=benchmark_code,
        search=q, order_by=order_by, skip=skip, limit=limit
    )
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": items
    }

@router.get("/categories", response_model=List[str])
async def list_categories(
    session: AsyncSession = Depends(get_db),
    current_user: str = Depends(security.get_current_user),
):
    """Return distinct scheme_category values from active funds."""
    return await crud.get_distinct_categories(session)


@router.get("/categories/{category}/subcategories", response_model=List[str])
async def list_subcategories(
    category: str,
    session: AsyncSession = Depends(get_db),
    current_user: str = Depends(security.get_current_user),
):
    """Return distinct subcategories for a given category."""
    return await crud.get_distinct_subcategories(session, category)


@router.get("/compare", response_model=schemas.ComparisonResponse)
async def compare_funds(
    codes: str = Query(..., description="Comma-separated scheme codes for comparison"),
    session: AsyncSession = Depends(get_db),
    current_user: str = Depends(security.get_current_user),
):
    """Compare multiple funds (max 4). Enforces same category matching."""
    # 1. Parse and validate codes
    scheme_codes = [c.strip() for c in codes.split(",") if c.strip()]
    if len(scheme_codes) < 2:
        raise HTTPException(status_code=400, detail="At least 2 funds are required for comparison")
    if len(scheme_codes) > 4:
        raise HTTPException(status_code=400, detail="Maximum 4 funds can be compared at a time")

    # 2. Fetch all fund masters in batch
    results = await crud.get_fund_masters_by_codes(session, scheme_codes)
    masters_map = {m.scheme_code: m for m in results}
    masters = [masters_map.get(code) for code in scheme_codes]
    
    for i, master in enumerate(masters):
        if not master:
            raise HTTPException(status_code=404, detail=f"Fund with code {scheme_codes[i]} not found")

    # 3. Validate same top-level category (hard requirement).
    # Subcategory mismatch is allowed but surfaced as a warning.
    main_cat = masters[0].scheme_category
    for m in masters[1:]:
        if m.scheme_category != main_cat:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Category mismatch: all funds must share the same scheme_category. "
                    f"Expected '{main_cat}', got '{m.scheme_category}'."
                ),
            )

    subcategory_warning = None
    subcategories = {m.scheme_subcategory for m in masters}
    if len(subcategories) > 1:
        subcategory_warning = (
            "Funds span multiple subcategories — comparison may not be apples-to-apples."
        )

    # 4. Use optimized analytics helper
    comparison_data = await analytics.get_comparison_data(session, scheme_codes)

    # 5. Compute recommendation ranking
    all_metrics = [f["metrics"] for f in comparison_data["funds"]]
    ranking = analytics.rank_funds_for_comparison(all_metrics, scheme_codes)
    comparison_data["ranking"] = ranking

    if subcategory_warning:
        comparison_data["warning"] = subcategory_warning
    return comparison_data

@router.get("/{scheme_code}", response_model=schemas.FundMasterRead)
async def read_fund(
    scheme_code: str,
    session: AsyncSession = Depends(get_db),
    current_user: str = Depends(security.get_current_user),
):
    """Get details for a specific fund by its code."""
    fund = await crud.get_fund_master_by_code(session, scheme_code)
    if not fund:
        raise HTTPException(status_code=404, detail=f"Fund with scheme_code {scheme_code} not found")
    return fund

@router.get("/{scheme_code}/similar", response_model=List[schemas.FundMasterRead])
async def get_similar_funds(
    scheme_code: str,
    session: AsyncSession = Depends(get_db),
    current_user: str = Depends(security.get_current_user),
):
    """Get funds with the same category and subcategory."""
    return await crud.get_similar_funds(session, scheme_code)

@router.put("/{scheme_code}", response_model=schemas.FundMasterRead)
async def update_fund(
    scheme_code: str,
    fund_in: schemas.FundMasterUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: str = Depends(security.get_current_user)
):
    """Update fund details (Requires Auth)."""
    result = await crud.update_fund_master(session, scheme_code, fund_in)
    if not result:
        raise HTTPException(status_code=404, detail="Fund not found")
    return result

@router.delete("/{scheme_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fund(
    scheme_code: str, 
    session: AsyncSession = Depends(get_db),
    current_user: str = Depends(security.get_current_user)
):
    """Delete (deactivate) a fund (Requires Auth)."""
    result = await crud.delete_fund_master(session, scheme_code)
    if not result:
        raise HTTPException(status_code=404, detail="Fund not found")
    return None
