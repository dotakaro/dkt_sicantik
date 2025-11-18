# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class SicantikPermit(models.Model):
    """
    SICANTIK Permit Model
    
    Stores permit data synced from SICANTIK system.
    Includes expiry tracking and WhatsApp notification triggers.
    """
    _name = 'sicantik.permit'
    _description = 'SICANTIK Permit'
    _rec_name = 'registration_id'
    _order = 'create_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    # Basic Information
    registration_id = fields.Char(
        string='Registration ID',
        required=True,
        index=True,
        readonly=True,
        help='Unique registration ID from SICANTIK (pendaftaran_id)'
    )
    
    permit_number = fields.Char(
        string='Permit Number',
        index=True,
        tracking=True,
        help='Official permit number (no_surat)'
    )
    
    applicant_name = fields.Char(
        string='Nama Pemohon',
        tracking=True,
        help='Nama pemohon izin dari SICANTIK (n_pemohon)'
    )
    
    permit_type_name = fields.Char(
        string='Permit Type',
        required=True,
        tracking=True,
        help='Type of permit (n_perizinan)'
    )
    
    permit_type_id = fields.Many2one(
        'sicantik.permit.type',
        string='Permit Type (Linked)',
        help='Linked permit type master data'
    )
    
    # Partner Integration
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        help='Linked partner/contact'
    )
    
    # Phone field for WhatsApp notifications
    mobile = fields.Char(
        string='Mobile',
        compute='_compute_mobile',
        readonly=True,
        store=False,
        help='Mobile number from linked partner (for WhatsApp notifications)'
    )
    
    @api.depends('partner_id')
    def _compute_mobile(self):
        """Compute mobile number from partner"""
        for record in self:
            if record.partner_id:
                # Access mobile field directly, will be None if field doesn't exist
                record.mobile = getattr(record.partner_id, 'mobile', False)
            else:
                record.mobile = False
    
    # Dates
    issue_date = fields.Date(
        string='Issue Date',
        tracking=True,
        help='Date when permit was issued'
    )
    
    expiry_date = fields.Date(
        string='Expiry Date',
        tracking=True,
        index=True,
        help='Date when permit expires (d_berlaku_izin)'
    )
    
    received_date = fields.Date(
        string='Received Date',
        help='Date when application was received (d_terima_berkas)'
    )
    
    # Expiry Tracking
    days_until_expiry = fields.Integer(
        string='Days Until Expiry',
        compute='_compute_days_until_expiry',
        store=True,
        help='Number of days until permit expires'
    )
    
    expiry_status = fields.Selection([
        ('ok', 'OK (>60 days)'),
        ('warning', 'Warning (31-60 days)'),
        ('critical', 'Critical (1-30 days)'),
        ('expired', 'Expired')
    ], string='Expiry Status', compute='_compute_expiry_status', store=True)
    
    # Expiry Notification Tracking
    expiry_notified_90 = fields.Boolean(
        string='Notified 90 Days',
        default=False,
        help='WhatsApp notification sent at 90 days before expiry'
    )
    
    expiry_notified_60 = fields.Boolean(
        string='Notified 60 Days',
        default=False,
        help='WhatsApp notification sent at 60 days before expiry'
    )
    
    expiry_notified_30 = fields.Boolean(
        string='Notified 30 Days',
        default=False,
        help='WhatsApp notification sent at 30 days before expiry'
    )
    
    expiry_notified_7 = fields.Boolean(
        string='Notified 7 Days',
        default=False,
        help='WhatsApp notification sent at 7 days before expiry'
    )
    
    # Status
    status = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('renewed', 'Renewed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='active', required=True, tracking=True)
    
    # Renewal
    is_renewal = fields.Boolean(
        string='Is Renewal',
        default=False,
        help='Indicates if this is a renewal of existing permit'
    )
    
    original_permit_id = fields.Many2one(
        'sicantik.permit',
        string='Original Permit',
        help='Original permit if this is a renewal'
    )
    
    renewal_permit_id = fields.Many2one(
        'sicantik.permit',
        string='Renewal Permit',
        help='Renewal permit if this was renewed'
    )
    
    # Sync Information
    last_sync_date = fields.Datetime(
        string='Last Sync Date',
        readonly=True,
        help='Last time this record was synced from SICANTIK'
    )
    
    # Additional Fields
    notes = fields.Text(string='Notes')
    
    _sql_constraints = [
        ('registration_id_unique', 'unique(registration_id)', 
         'Registration ID must be unique!')
    ]
    
    @api.depends('expiry_date')
    def _compute_days_until_expiry(self):
        """Calculate days until expiry"""
        today = fields.Date.today()
        
        for record in self:
            if record.expiry_date:
                delta = record.expiry_date - today
                record.days_until_expiry = delta.days
            else:
                record.days_until_expiry = 0
    
    @api.depends('days_until_expiry', 'status')
    def _compute_expiry_status(self):
        """Compute expiry status based on days remaining"""
        for record in self:
            if record.status == 'expired':
                record.expiry_status = 'expired'
            elif not record.expiry_date:
                record.expiry_status = False
            elif record.days_until_expiry < 0:
                record.expiry_status = 'expired'
            elif record.days_until_expiry <= 30:
                record.expiry_status = 'critical'
            elif record.days_until_expiry <= 60:
                record.expiry_status = 'warning'
            else:
                record.expiry_status = 'ok'
    
    def write(self, vals):
        """Override to trigger WhatsApp notifications"""
        result = super().write(vals)
        
        # Check if status changed to 'done'
        if vals.get('status') == 'done':
            self._send_permit_ready_notification()
        
        # Check if status changed
        if 'status' in vals:
            self._send_status_update_notification(vals.get('status'))
        
        # Check if renewal approved
        if vals.get('is_renewal') and vals.get('status') == 'done':
            self._send_renewal_approved_notification()
        
        return result
    
    def _send_permit_ready_notification(self):
        """Send WhatsApp notification when permit is ready"""
        # Will be implemented in sicantik_whatsapp module
        pass
    
    def _send_status_update_notification(self, new_status):
        """Send WhatsApp notification when status changes"""
        # Will be implemented in sicantik_whatsapp module
        pass
    
    def _send_renewal_approved_notification(self):
        """Send WhatsApp notification when renewal is approved"""
        # Will be implemented in sicantik_whatsapp module
        pass
    
    @api.model
    def cron_check_expiring_permits(self):
        """
        Cron job to check permits approaching expiry
        Run daily at 09:00 AM
        
        NOTE: This uses WORKAROUND solution (two-step API process)
        TODO: Migrate to optimized solution after API update
        """
        today = fields.Date.today()
        
        # Define notification thresholds
        thresholds = [
            (90, 'expiry_notified_90'),
            (60, 'expiry_notified_60'),
            (30, 'expiry_notified_30'),
            (7, 'expiry_notified_7')
        ]
        
        _logger.info('Starting expiry check cron job...')
        
        # WORKAROUND: Sync expiry dates first
        connector = self.env['sicantik.connector'].search([('active', '=', True)], limit=1)
        if connector:
            _logger.info('Syncing expiry dates (workaround)...')
            try:
                connector.sync_expiry_dates_workaround()
            except Exception as e:
                _logger.error(f'Error syncing expiry dates: {str(e)}')
        
        for days, field_name in thresholds:
            target_date = today + timedelta(days=days)
            
            # Find permits expiring on target date that haven't been notified
            permits = self.search([
                ('expiry_date', '=', target_date),
                ('status', '=', 'active'),
                (field_name, '=', False)
            ])
            
            _logger.info(f'Found {len(permits)} permits expiring in {days} days')
            
            for permit in permits:
                try:
                    # Send WhatsApp notification
                    # Will be implemented in sicantik_whatsapp module
                    _logger.info(f'Would send notification for permit {permit.permit_number} ({days} days)')
                    
                    # Mark as notified
                    permit.write({field_name: True})
                
                except Exception as e:
                    _logger.error(f'Error sending notification for {permit.permit_number}: {str(e)}')
        
        _logger.info('Expiry check cron job completed')
    
    @api.model
    def cron_update_expired_permits(self):
        """
        Cron job to update status of expired permits
        Run daily at 00:00 AM
        """
        today = fields.Date.today()
        
        expired_permits = self.search([
            ('expiry_date', '<', today),
            ('status', '=', 'active')
        ])
        
        if expired_permits:
            expired_permits.write({'status': 'expired'})
            _logger.info(f'Updated {len(expired_permits)} permits to expired status')
    
    def action_mark_as_renewed(self):
        """Mark permit as renewed"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Renewal',
            'res_model': 'sicantik.permit',
            'view_mode': 'form',
            'context': {
                'default_is_renewal': True,
                'default_original_permit_id': self.id,
                'default_applicant_name': self.applicant_name,
                'default_permit_type_name': self.permit_type_name,
                'default_partner_id': self.partner_id.id,
            },
            'target': 'current',
        }
    
    def action_view_history(self):
        """View permit history"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Permit History',
            'res_model': 'sicantik.permit',
            'view_mode': 'list,form',
            'domain': [
                '|',
                ('original_permit_id', '=', self.id),
                ('id', '=', self.original_permit_id.id)
            ],
            'context': {},
        }
    
    def action_send_test_notification(self):
        """Send test WhatsApp notification"""
        self.ensure_one()
        
        # Cek apakah modul sicantik_whatsapp sudah terinstall
        whatsapp_module = self.env['ir.module.module'].search([
            ('name', '=', 'sicantik_whatsapp'),
            ('state', '=', 'installed')
        ], limit=1)
        
        if not whatsapp_module:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Test Notification',
                    'message': 'WhatsApp notification feature akan tersedia setelah modul sicantik_whatsapp diinstall. Silakan install modul sicantik_whatsapp terlebih dahulu.',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        # Jika modul sudah terinstall, method ini akan di-override oleh sicantik_whatsapp
        # Tapi sebagai fallback, tampilkan pesan bahwa fitur tersedia
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Test Notification',
                'message': 'Fitur WhatsApp notification tersedia. Silakan pastikan template WhatsApp sudah di-setup dan approved.',
                'type': 'info',
                'sticky': False,
            }
        }

