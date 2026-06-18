"""add paper trading tables

Revision ID: 7b19ddec73b8
Revises: 0001_initial
Create Date: 2026-06-18 13:34:09.149655

"""
from alembic import op
import sqlalchemy as sa
import uuid
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '7b19ddec73b8'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'paper_positions',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('symbol', sa.String(16), nullable=False),
        sa.Column('side', sa.String(8), default='long', nullable=False),
        sa.Column('status', sa.String(16), default='open', nullable=False),
        sa.Column('entry_price', sa.Float(), nullable=True),
        sa.Column('entry_date', sa.DateTime(), nullable=True),
        sa.Column('shares', sa.Float(), nullable=True),
        sa.Column('notional', sa.Float(), nullable=True),
        sa.Column('exit_price', sa.Float(), nullable=True),
        sa.Column('exit_date', sa.DateTime(), nullable=True),
        sa.Column('realized_pnl', sa.Float(), nullable=True),
        sa.Column('realized_return', sa.Float(), nullable=True),
        sa.Column('stop_loss', sa.Float(), nullable=True),
        sa.Column('take_profit', sa.Float(), nullable=True),
        sa.Column('max_hold_days', sa.Integer(), default=4),
        sa.Column('planned_exit_date', sa.DateTime(), nullable=True),
        sa.Column('stock_pick_id', sa.String(36), sa.ForeignKey('stock_picks.id'), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), default=dict),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_paper_positions_symbol', 'paper_positions', ['symbol'])
    op.create_index('ix_paper_positions_status', 'paper_positions', ['status'])
    op.create_index('ix_paper_positions_entry_date', 'paper_positions', ['entry_date'])
    op.create_index('ix_paper_positions_status_symbol', 'paper_positions', ['status', 'symbol'])
    op.create_index('ix_paper_positions_status_entry_date', 'paper_positions', ['status', 'entry_date'])
    op.create_index('ix_paper_positions_stock_pick_id', 'paper_positions', ['stock_pick_id'])

    op.create_table(
        'broker_orders',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('position_id', sa.String(36), sa.ForeignKey('paper_positions.id'), nullable=True),
        sa.Column('broker', sa.String(32), default='alpaca', nullable=False),
        sa.Column('side', sa.String(8), nullable=False),
        sa.Column('order_type', sa.String(16), nullable=False),
        sa.Column('symbol', sa.String(16), nullable=False),
        sa.Column('qty', sa.Float(), nullable=True),
        sa.Column('notional', sa.Float(), nullable=True),
        sa.Column('limit_price', sa.Float(), nullable=True),
        sa.Column('stop_price', sa.Float(), nullable=True),
        sa.Column('broker_order_id', sa.String(64), nullable=True),
        sa.Column('status', sa.String(16), default='pending', nullable=False),
        sa.Column('raw_response', sa.JSON(), default=dict),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_broker_orders_symbol', 'broker_orders', ['symbol'])
    op.create_index('ix_broker_orders_position_id', 'broker_orders', ['position_id'])
    op.create_index('ix_broker_orders_broker_order_id', 'broker_orders', ['broker_order_id'])
    op.create_index('ix_broker_orders_status', 'broker_orders', ['status'])


def downgrade():
    op.drop_index('ix_broker_orders_status', table_name='broker_orders')
    op.drop_index('ix_broker_orders_broker_order_id', table_name='broker_orders')
    op.drop_index('ix_broker_orders_position_id', table_name='broker_orders')
    op.drop_index('ix_broker_orders_symbol', table_name='broker_orders')
    op.drop_table('broker_orders')
    op.drop_index('ix_paper_positions_stock_pick_id', table_name='paper_positions')
    op.drop_index('ix_paper_positions_status_entry_date', table_name='paper_positions')
    op.drop_index('ix_paper_positions_status_symbol', table_name='paper_positions')
    op.drop_index('ix_paper_positions_entry_date', table_name='paper_positions')
    op.drop_index('ix_paper_positions_status', table_name='paper_positions')
    op.drop_index('ix_paper_positions_symbol', table_name='paper_positions')
    op.drop_table('paper_positions')
