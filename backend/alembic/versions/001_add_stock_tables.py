"""add_stock_tables

Revision ID: 001
Revises:
Create Date: 2026-04-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite: tables are created by migration 003 — skip all PostgreSQL-specific DDL
    connection = op.get_bind()
    if connection.dialect.name == 'sqlite':
        return

    # Create pg_trgm extension for trigram search support
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # Idempotency guard: if stock tables were already created by Base.metadata.create_all
    # (e.g. via main.py lifespan or db_init.py), skip all CREATE TABLE/INDEX statements.
    # Alembic will still stamp revision '001' in alembic_version because upgrade() returns
    # without raising, so subsequent `alembic upgrade head` calls will be no-ops.
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_tables = set(inspector.get_table_names())
    if 'stocks' in existing_tables:
        return

    # Table 1: stocks
    op.create_table(
        'stocks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False, unique=True),
        sa.Column('nse_symbol', sa.String(20)),
        sa.Column('bse_code', sa.String(10)),
        sa.Column('yf_symbol', sa.String(30), nullable=False),
        sa.Column('screener_slug', sa.String(50)),
        sa.Column('company_name', sa.String(255), nullable=False),
        sa.Column('sector', sa.String(100)),
        sa.Column('industry', sa.String(100)),
        sa.Column('market_cap_cat', sa.String(10)),
        sa.Column('is_index', sa.Boolean(), server_default=sa.literal(False)),
        sa.Column('is_active', sa.Boolean(), server_default=sa.literal(True)),
        sa.Column('data_quality', sa.String(10), server_default='OK'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_stocks_sector', 'stocks', ['sector'], postgresql_where=sa.text('is_active = TRUE'))
    op.create_index('idx_stocks_market_cap', 'stocks', ['market_cap_cat'], postgresql_where=sa.text('is_active = TRUE'))
    op.create_index('idx_stocks_fts', 'stocks', ['company_name', 'symbol'],
                   postgresql_using='gin',
                   postgresql_ops={'company_name': 'gin_trgm_ops', 'symbol': 'gin_trgm_ops'})

    # Table 2: price_data
    op.create_table(
        'price_data',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('price_date', sa.Date(), nullable=False),
        sa.Column('open', sa.Numeric(12, 4)),
        sa.Column('high', sa.Numeric(12, 4)),
        sa.Column('low', sa.Numeric(12, 4)),
        sa.Column('close', sa.Numeric(12, 4), nullable=False),
        sa.Column('adj_close', sa.Numeric(12, 4)),
        sa.Column('volume', sa.BigInteger()),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_id', 'price_date', name='uq_price_stock_date')
    )
    op.create_index('idx_price_stock_date', 'price_data', ['stock_id', 'price_date'], postgresql_using='btree')
    op.create_index('idx_price_date', 'price_data', ['price_date'], postgresql_using='btree')

    # Table 3: financial_statements
    op.create_table(
        'financial_statements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('statement_type', sa.String(5), nullable=False),
        sa.Column('period_type', sa.String(10), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('currency', sa.String(5), server_default='INR'),
        sa.Column('data', postgresql.JSONB(), nullable=False),
        sa.Column('raw_data', postgresql.JSONB()),
        sa.Column('scraped_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('raw_checksum', sa.String(64)),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_id', 'statement_type', 'period_type', 'period_end', name='uq_fs')
    )
    op.create_index('idx_fs_stock_type', 'financial_statements', ['stock_id', 'statement_type', 'period_end'])
    op.create_index('idx_fs_data_gin', 'financial_statements', ['data'], postgresql_using='gin')

    # Table 4: shareholding_pattern
    op.create_table(
        'shareholding_pattern',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('promoter_pct', sa.Numeric(6, 3)),
        sa.Column('fii_pct', sa.Numeric(6, 3)),
        sa.Column('dii_pct', sa.Numeric(6, 3)),
        sa.Column('public_pct', sa.Numeric(6, 3)),
        sa.Column('pledged_pct', sa.Numeric(6, 3)),
        sa.Column('promoter_change', sa.Numeric(6, 3)),
        sa.Column('fii_change', sa.Numeric(6, 3)),
        sa.Column('scraped_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_id', 'period_end', name='uq_sh')
    )
    op.create_index('idx_sh_stock_period', 'shareholding_pattern', ['stock_id', 'period_end'])

    # Table 5: financial_ratios
    op.create_table(
        'financial_ratios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('period_type', sa.String(10), nullable=False),
        sa.Column('pe_ratio', sa.Numeric(10, 3)),
        sa.Column('pb_ratio', sa.Numeric(10, 3)),
        sa.Column('ps_ratio', sa.Numeric(10, 3)),
        sa.Column('ev_ebitda', sa.Numeric(10, 3)),
        sa.Column('peg_ratio', sa.Numeric(10, 3)),
        sa.Column('roe', sa.Numeric(10, 3)),
        sa.Column('roce', sa.Numeric(10, 3)),
        sa.Column('roa', sa.Numeric(10, 3)),
        sa.Column('gross_margin', sa.Numeric(10, 3)),
        sa.Column('ebitda_margin', sa.Numeric(10, 3)),
        sa.Column('pat_margin', sa.Numeric(10, 3)),
        sa.Column('debt_equity', sa.Numeric(10, 3)),
        sa.Column('interest_cov', sa.Numeric(10, 3)),
        sa.Column('current_ratio', sa.Numeric(10, 3)),
        sa.Column('quick_ratio', sa.Numeric(10, 3)),
        sa.Column('revenue_growth', sa.Numeric(10, 3)),
        sa.Column('pat_growth', sa.Numeric(10, 3)),
        sa.Column('eps_growth', sa.Numeric(10, 3)),
        sa.Column('eps', sa.Numeric(12, 4)),
        sa.Column('book_value_ps', sa.Numeric(12, 4)),
        sa.Column('dividend_yield', sa.Numeric(8, 4)),
        sa.Column('cfo_to_pat', sa.Numeric(10, 3)),
        sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_id', 'period_end', 'period_type', name='uq_ratios')
    )
    op.create_index('idx_ratios_screener', 'financial_ratios', ['stock_id', 'roe', 'pe_ratio', 'debt_equity', 'pat_margin'])
    op.create_index('idx_ratios_period', 'financial_ratios', ['stock_id', 'period_end'])

    # Table 6: technical_indicators
    op.create_table(
        'technical_indicators',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('ind_date', sa.Date(), nullable=False),
        sa.Column('timeframe', sa.String(5), nullable=False),
        sa.Column('sma_20', sa.Numeric(12, 4)),
        sa.Column('sma_50', sa.Numeric(12, 4)),
        sa.Column('sma_200', sa.Numeric(12, 4)),
        sa.Column('ema_9', sa.Numeric(12, 4)),
        sa.Column('ema_21', sa.Numeric(12, 4)),
        sa.Column('ema_50', sa.Numeric(12, 4)),
        sa.Column('rsi_14', sa.Numeric(8, 4)),
        sa.Column('macd_line', sa.Numeric(12, 4)),
        sa.Column('macd_signal', sa.Numeric(12, 4)),
        sa.Column('macd_hist', sa.Numeric(12, 4)),
        sa.Column('bb_upper', sa.Numeric(12, 4)),
        sa.Column('bb_middle', sa.Numeric(12, 4)),
        sa.Column('bb_lower', sa.Numeric(12, 4)),
        sa.Column('atr_14', sa.Numeric(12, 4)),
        sa.Column('adx_14', sa.Numeric(8, 4)),
        sa.Column('stoch_k', sa.Numeric(8, 4)),
        sa.Column('stoch_d', sa.Numeric(8, 4)),
        sa.Column('volume_sma_20', sa.BigInteger()),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_id', 'timeframe', 'ind_date', name='uq_ti')
    )
    op.create_index('idx_ti_stock_tf_date', 'technical_indicators', ['stock_id', 'timeframe', 'ind_date'])

    # Table 7: detected_patterns
    op.create_table(
        'detected_patterns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('pattern_type', sa.String(30), nullable=False),
        sa.Column('timeframe', sa.String(5), nullable=False),
        sa.Column('detected_on', sa.Date(), nullable=False),
        sa.Column('pattern_start', sa.Date(), nullable=False),
        sa.Column('pattern_end', sa.Date(), nullable=False),
        sa.Column('breakout_level', sa.Numeric(12, 4)),
        sa.Column('direction', sa.String(10)),
        sa.Column('confidence', sa.Numeric(4, 3)),
        sa.Column('is_active', sa.Boolean(), server_default=sa.literal(True)),
        sa.Column('metadata', postgresql.JSONB()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_patterns_stock', 'detected_patterns', ['stock_id', 'detected_on'])
    op.create_index('idx_patterns_active', 'detected_patterns', ['is_active'], postgresql_where=sa.text('is_active = TRUE'))
    op.create_index('idx_patterns_type', 'detected_patterns', ['pattern_type', 'detected_on'])

    # Table 8: stock_ratings
    op.create_table(
        'stock_ratings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('rated_on', sa.Date(), nullable=False),
        sa.Column('total_score', sa.Numeric(6, 3)),
        sa.Column('rating_label', sa.String(15)),
        sa.Column('fundamental_score', sa.Numeric(6, 3)),
        sa.Column('valuation_score', sa.Numeric(6, 3)),
        sa.Column('technical_score', sa.Numeric(6, 3)),
        sa.Column('momentum_score', sa.Numeric(6, 3)),
        sa.Column('quality_score', sa.Numeric(6, 3)),
        sa.Column('shareholding_score', sa.Numeric(6, 3)),
        sa.Column('score_breakdown', postgresql.JSONB()),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_id', 'rated_on', name='uq_rating')
    )
    op.create_index('idx_ratings_stock', 'stock_ratings', ['stock_id', 'rated_on'])
    op.create_index('idx_ratings_label', 'stock_ratings', ['rating_label', 'rated_on'])

    # Table 9: pipeline_audit
    op.create_table(
        'pipeline_audit',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_name', sa.String(60), nullable=False),
        sa.Column('stock_id', sa.Integer()),
        sa.Column('status', sa.String(10), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('ended_at', sa.DateTime(timezone=True)),
        sa.Column('records_in', sa.Integer(), server_default=sa.literal(0)),
        sa.Column('records_out', sa.Integer(), server_default=sa.literal(0)),
        sa.Column('error_msg', sa.Text()),
        sa.Column('metadata', postgresql.JSONB()),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_audit_job_status', 'pipeline_audit', ['job_name', 'started_at'])
    op.create_index('idx_audit_failed', 'pipeline_audit', ['status'], postgresql_where=sa.text("status = 'FAILED'"))


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == 'sqlite':
        return
    op.drop_index('idx_audit_failed', table_name='pipeline_audit')
    op.drop_index('idx_audit_job_status', table_name='pipeline_audit')
    op.drop_table('pipeline_audit')

    op.drop_index('idx_ratings_label', table_name='stock_ratings')
    op.drop_index('idx_ratings_stock', table_name='stock_ratings')
    op.drop_table('stock_ratings')

    op.drop_index('idx_patterns_type', table_name='detected_patterns')
    op.drop_index('idx_patterns_active', table_name='detected_patterns')
    op.drop_index('idx_patterns_stock', table_name='detected_patterns')
    op.drop_table('detected_patterns')

    op.drop_index('idx_ti_stock_tf_date', table_name='technical_indicators')
    op.drop_table('technical_indicators')

    op.drop_index('idx_ratios_period', table_name='financial_ratios')
    op.drop_index('idx_ratios_screener', table_name='financial_ratios')
    op.drop_table('financial_ratios')

    op.drop_index('idx_sh_stock_period', table_name='shareholding_pattern')
    op.drop_table('shareholding_pattern')

    op.drop_index('idx_fs_data_gin', table_name='financial_statements')
    op.drop_index('idx_fs_stock_type', table_name='financial_statements')
    op.drop_table('financial_statements')

    op.drop_index('idx_price_date', table_name='price_data')
    op.drop_index('idx_price_stock_date', table_name='price_data')
    op.drop_table('price_data')

    op.drop_index('idx_stocks_fts', table_name='stocks')
    op.drop_index('idx_stocks_market_cap', table_name='stocks')
    op.drop_index('idx_stocks_sector', table_name='stocks')
    op.drop_table('stocks')
