from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class PropertyDashboard(models.Model):
    _name = 'property.dashboard'
    _description = 'Property Dashboard'

    # Fields for totals
    total_properties = fields.Integer(string='Total Properties', compute='_compute_totals')
    total_in_lease = fields.Integer(string='Total In Lease', compute='_compute_totals')
    total_tenants = fields.Integer(string='Total Tenants', compute='_compute_totals')
    total_utility_income = fields.Float(string='Total Utility Income', compute='_compute_totals')
    total_maintenance_income = fields.Float(string='Total Maintenance Income', compute='_compute_totals')
    total_payments_invoiced = fields.Float(string='Total Payments (Invoiced)', compute='_compute_totals')
    total_draft_payments = fields.Float(string='Total Draft Payments', compute='_compute_totals')
    total_available_properties = fields.Integer(string='Total Available Properties', compute='_compute_totals')

    # Fields for utility usage
    electricity_usage = fields.Float(string='Electricity Usage', compute='_compute_usage')
    water_usage = fields.Float(string='Water Usage', compute='_compute_usage')

    # Fields for recent records
    recent_tenants = fields.One2many('property.tenant', string='Recent Tenants', compute='_compute_recent_tenants')
    recent_payments = fields.One2many('property.payment', string='Recent Payments', compute='_compute_recent_payments')
    recent_maintenances = fields.One2many('property.maintenance', string='Recent Maintenance', compute='_compute_recent_maintenances')
    active_leases = fields.One2many('property.lease', string='Active Leases', compute='_compute_active_leases')

    # Chart data fields
    properties_overview = fields.Json(string='Properties Overview', compute='_compute_properties_overview')
    income_breakdown = fields.Json(string='Income Breakdown', compute='_compute_income_breakdown')
    tenant_statistics = fields.Json(string='Tenant Statistics', compute='_compute_tenant_statistics')
    utility_usage_comparison = fields.Json(string='Utility Usage Comparison', compute='_compute_utility_usage_comparison')
    active_leases_status = fields.Json(string='Active Leases Status', compute='_compute_active_leases_status')
    payments_analysis = fields.Json(string='Payments Analysis', compute='_compute_payments_analysis')
    monthly_utility_usage_trend = fields.Json(string='Monthly Utility Usage Trend', compute='_compute_monthly_utility_usage_trend')

    @api.depends('total_properties', 'total_in_lease', 'total_available_properties')
    def _compute_properties_overview(self):
        for record in self:
            record.properties_overview = {
                'total_properties': record.total_properties,
                'total_in_lease': record.total_in_lease,
                'total_available_properties': record.total_available_properties,
            }

    @api.depends('total_utility_income', 'total_maintenance_income', 'total_payments_invoiced', 'total_draft_payments')
    def _compute_income_breakdown(self):
        for record in self:
            record.income_breakdown = {
                'utility_income': record.total_utility_income,
                'maintenance_income': record.total_maintenance_income,
                'payments_invoiced': record.total_payments_invoiced,
                'draft_payments': record.total_draft_payments,
            }

    @api.depends('total_tenants')
    def _compute_tenant_statistics(self):
        # This should return a time-series data structure to visualize changes over time
        tenant_records = self.env['property.tenant'].read_group([], ['create_date:month'], ['create_date:month'])
        record.tenant_statistics = {r['create_date:month']: r['__count'] for r in tenant_records}

    @api.depends('electricity_usage', 'water_usage')
    def _compute_utility_usage_comparison(self):
        for record in self:
            record.utility_usage_comparison = {
                'electricity_usage': record.electricity_usage,
                'water_usage': record.water_usage,
            }

    @api.depends('active_leases')
    def _compute_active_leases_status(self):
        active_leases_data = self.env['property.lease'].read_group([], ['status:count'], ['status'])
        record.active_leases_status = {r['status']: r['status_count'] for r in active_leases_data}

    @api.depends('total_payments_invoiced', 'total_draft_payments')
    def _compute_payments_analysis(self):
        payment_records = self.env['property.payment'].read_group([], ['payment_date:month', 'amount'], [])
        record.payments_analysis = {
            'invoiced_payments': [r['amount'] for r in payment_records if r['status'] == 'invoiced'],
            'draft_payments': [r['amount'] for r in payment_records if r['status'] == 'draft'],
        }

    @api.depends('electricity_usage', 'water_usage')
    def _compute_monthly_utility_usage_trend(self):
        monthly_data = {}
        for record in self:
            electricity_records = self.env['property.utility.record'].read_group(
                [('utility_type', '=', 'electricity')],
                ['amount_used', 'date:month'],
                ['date:month']
            )
            water_records = self.env['property.utility.record'].read_group(
                [('utility_type', '=', 'water')],
                ['amount_used', 'date:month'],
                ['date:month']
            )
            monthly_data['electricity'] = {r['date:month']: r['amount_used'] for r in electricity_records}
            monthly_data['water'] = {r['date:month']: r['amount_used'] for r in water_records}
            record.monthly_utility_usage_trend = monthly_data

    @api.depends('total_properties', 'total_in_lease', 'total_tenants', 'total_utility_income',
                 'total_maintenance_income', 'total_payments_invoiced', 'total_draft_payments', 
                 'total_available_properties')
    def _compute_totals(self):
        for record in self:
            try:
                _logger.debug("Calculating totals for dashboard...")

                # Total Properties
                record.total_properties = self.env['property.management'].search_count([])

                # Total In Lease
                record.total_in_lease = self.env['property.lease'].search_count([('status', '=', 'active')])

                # Total Tenants
                record.total_tenants = self.env['property.tenant'].search_count([])

                # Utility Income
                utility_records = self.env['property.utility.record'].read_group([], ['subtotal'], [])
                record.total_utility_income = sum(r['subtotal'] for r in utility_records) if utility_records else 0.0

                # Maintenance Income
                maintenance_records = self.env['property.maintenance'].read_group([], ['charge'], [])
                record.total_maintenance_income = sum(r['charge'] for r in maintenance_records) if maintenance_records else 0.0

                # Payments Invoiced
                payments_invoiced = self.env['property.payment'].read_group([('status', '=', 'invoiced')], ['amount'], [])
                record.total_payments_invoiced = sum(r['amount'] for r in payments_invoiced) if payments_invoiced else 0.0

                # Draft Payments
                payments_draft = self.env['property.payment'].read_group([('status', '=', 'draft')], ['amount'], [])
                record.total_draft_payments = sum(r['amount'] for r in payments_draft) if payments_draft else 0.0

                # Available Properties
                record.total_available_properties = self.env['property.management'].search_count([('lease_ids', '=', False)])

            except Exception as e:
                _logger.error(f"Error computing totals for dashboard: {str(e)}")
                raise ValidationError("An error occurred while calculating dashboard totals.")

    @api.depends('electricity_usage', 'water_usage')
    def _compute_usage(self):
        for record in self:
            electricity_records = self.env['property.utility.record'].read_group(
                [('utility_type', '=', 'electricity')], 
                ['amount_used'], 
                []
            )
            record.electricity_usage = sum(r['amount_used'] for r in electricity_records) if electricity_records else 0.0
            
            water_records = self.env['property.utility.record'].read_group(
                [('utility_type', '=', 'water')], 
                ['amount_used'], 
                []
            )
            record.water_usage = sum(r['amount_used'] for r in water_records) if water_records else 0.0

    @api.depends('recent_tenants')
    def _compute_recent_tenants(self):
        self.recent_tenants = self.env['property.tenant'].search([], order='id desc', limit=5)

    @api.depends('recent_payments')
    def _compute_recent_payments(self):
        self.recent_payments = self.env['property.payment'].search([], order='payment_date desc', limit=5)

    @api.depends('recent_maintenances')
    def _compute_recent_maintenances(self):
        self.recent_maintenances = self.env['property.maintenance'].search([], order='maintenance_date desc', limit=5)

    @api.depends('active_leases')
    def _compute_active_leases(self):
        self.active_leases = self.env['property.lease'].search([('status', '=', 'active')])

