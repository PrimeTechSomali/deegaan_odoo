from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class Payment(models.Model):
    _name = 'property.payment'
    _description = 'Lease Payment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    tenant_id = fields.Many2one('property.tenant', string='Tenant', required=True, track_visibility='onchange')
    property_id = fields.Many2one('property.management', string='Property', required=True, track_visibility='onchange')
    lease_id = fields.Many2one('property.lease', string='Lease')
    payment_date = fields.Date(string='Payment Date', required=True)
    amount = fields.Float(string='Amount', required=True)
    reference = fields.Char(string='Payment Reference', readonly=True, copy=False)
    sequence = fields.Integer(string='Sequence', default=0)
    payment_type = fields.Selection([
        ('rent', 'Rent'),
        ('electricity', 'Electricity'),
        ('water', 'Water'),
        ('assetloss', 'Assetloss'),
        ('maintenance', 'Maintenance'),
        ('gas', 'Gas'),
    ], string='Payment Type', required=True, track_visibility='onchange')
    
    # Updated status field to include 'paid'
    status = fields.Selection([
        ('draft', 'Draft'),
        ('due', 'Due'),
        ('confirmed', 'Confirmed'),
        ('invoiced', 'Invoiced'),
        ('paid', 'Paid'),  # New status added here
        ('canceled', 'Canceled'),
    ], string='Status', default='draft', tracking=True)
    
    invoice_line_id = fields.Many2one('account.move.line', string='Invoice Line', readonly=True)
    invoice_id = fields.Many2one('account.move', string='Invoice', readonly=True)

    name = fields.Char(string='Payment Name', compute='_compute_name', store=True)
    
    currency_id = fields.Many2one(
        'res.currency', 
        string='Currency', 
        default=lambda self: self.env.ref('base.USD').id,  # Set default currency to USD
        required=True
    )

    # Define a new field to store related payment IDs
    related_payment_ids = fields.Many2one('account.payment', string='Payment', readonly=True)

    @api.depends('reference')
    def _compute_name(self):
        for record in self:
            record.name = record.reference or f"Payment {record.id or 0}"

    @api.model
    def create(self, vals):
        if 'payment_type' not in vals or not vals.get('payment_type'):
            raise ValidationError("Payment Type is a mandatory field and must be set.")

        # Generate sequence number for the payment
        vals['sequence'] = self.env['ir.sequence'].next_by_code('property.payment') or 0
        vals['reference'] = f"PMY{vals['sequence']}"
        vals['status'] = 'draft'

        _logger.info(f"Creating a new payment record for tenant {vals.get('tenant_id')} with status 'draft'")
        return super(Payment, self).create(vals)

    def action_create_invoice(self):
        for payment in self:
            if payment.status != 'confirmed':
                raise ValidationError("Only confirmed payments can create an invoice.")

            invoice = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': payment.tenant_id.partner_id.id,
                'currency_id': payment.currency_id.id,
                'invoice_date': fields.Date.today(),
                'invoice_line_ids': [(0, 0, {
                    'product_id': 1,  # Ensure this ID exists
                    'name': f"{payment.payment_type} - {payment.reference}",
                    'quantity': 1,
                    'price_unit': payment.amount,
                })],
            })
            invoice.action_post()

            if invoice.invoice_line_ids:
                payment.invoice_line_id = invoice.invoice_line_ids[0].id

            payment.status = 'invoiced'
            payment.invoice_id = invoice.id  # Link invoice to payment
            _logger.info(f"Invoice created for payment {payment.id} using Rent Fee product.")

    def get_related_invoice(self):
        for payment in self:
            # Check if the payment has an associated invoice_id
            if not payment.invoice_id:
                _logger.warning(f"No invoice_id set for payment {payment.id}.")
                return None  # Return early if there's no invoice_id
            
            # Retrieve invoice_id from property_payment using the selected payment's id
            invoice_id = self.env['property.payment'].search(
                [('id', '=', payment.id)], 
                limit=1
            ).invoice_id

            if invoice_id:
                # Search for the corresponding invoice in account_move
                invoice = self.env['account.move'].search(
                    [('id', '=', invoice_id.id)], 
                    limit=1
                )
                if invoice:
                    _logger.info(f"Found invoice {invoice.id} for payment {payment.id}.")
                    return invoice
                else:
                    _logger.warning(f"No invoice found for payment {payment.id}, setting invoice_id to None.")
                    payment.invoice_id = None  # Clear the invoice_id if no invoice found
                    return None
            else:
                _logger.warning(f"No invoice_id found for payment {payment.id}.")
                payment.invoice_id = None  # Clear the invoice_id if not found
                return None

    def action_cancel(self):
        """Cancel the payment and change status to 'canceled'."""
        for payment in self:
            if payment.status == 'confirmed':
                raise ValidationError("Cannot cancel a confirmed payment.")
            payment.status = 'canceled'
            _logger.info(f"Payment {payment.id} canceled.")

    def action_confirm(self):
        """Confirm the payment and change status to 'confirmed'."""
        for payment in self:
            if payment.status == 'canceled':
                raise ValidationError("Cannot confirm a canceled payment.")
            payment.status = 'confirmed'
            _logger.info(f"Payment {payment.id} confirmed.")
    
    related_payments = fields.One2many(
        'account.payment', string='Related Payments',
        compute='_compute_related_payments'
    )

    @api.depends('invoice_id')
    def _compute_related_payments(self):
        for payment in self:
            if payment.invoice_id:
                # Use 'ref' to search for payments related to the specific invoice reference
                payment.related_payments = self.env['account.payment'].search([
                    ('ref', '=', payment.invoice_id.name)  # Assuming name is the ref value
                ])
            else:
                payment.related_payments = False

    def update_status_to_paid(self):
        for payment in self:
            # Check if there are related payments
            related_payments = self.env['account.payment'].search([
                ('ref', '=', payment.invoice_id.name)  # Match the payment reference
            ])
            if related_payments:
                # Update the status to 'paid'
                payment.status = 'paid'
                _logger.info(f"Payment status updated to 'paid' for {payment.id}.")
            else:
                # Raise a validation error if no related payments are found
                raise ValidationError(
                    f"No related payments found for payment {payment.id}. Status remains '{payment.status}'."
                )
