# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class TestMultiProviderWizard(models.TransientModel):
    """
    Wizard untuk testing multi-provider WhatsApp
    """
    _name = 'test.multi.provider.wizard'
    _description = 'Test Multi-Provider WhatsApp'
    
    # Test Configuration
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner Penerima',
        required=True,
        domain=[('phone', '!=', False)],
        help='Partner yang akan menerima test message'
    )
    
    template_key = fields.Selection([
        ('permit_ready', 'Izin Selesai Diproses'),
        ('permit_reminder', 'Peringatan Masa Berlaku'),
        ('status_update', 'Update Status'),
        ('renewal_approved', 'Perpanjangan Disetujui'),
        ('meta_opt_in_request', 'Request Meta Opt-In'),
    ], string='Template', required=True, default='permit_ready')
    
    force_provider_id = fields.Many2one(
        'sicantik.whatsapp.provider',
        string='Force Provider',
        help='Paksa menggunakan provider tertentu (kosongkan untuk auto-select)'
    )
    
    # Test Data
    test_permit_number = fields.Char(
        string='Nomor Izin (Test)',
        default='TEST-001/2025'
    )
    test_permit_type = fields.Char(
        string='Jenis Izin (Test)',
        default='Izin Usaha'
    )
    test_status = fields.Char(
        string='Status (Test)',
        default='Approved'
    )
    
    # Results
    test_result = fields.Text(
        string='Test Result',
        readonly=True
    )
    
    def action_run_test(self):
        """
        Jalankan test pengiriman via dispatcher
        """
        self.ensure_one()
        
        # Prepare context values
        context_values = {
            'partner_name': self.partner_id.name,
            'permit_number': self.test_permit_number,
            'permit_type': self.test_permit_type,
            'status': self.test_status,
            'expiry_date': '31/12/2025',
            'days_remaining': '90',
            'renewal_link': 'https://perizinan.karokab.go.id/perpanjangan',
            'contact_info': '0628-20XXX',
            'new_status': self.test_status,
            'update_date': fields.Date.today().strftime('%d/%m/%Y'),
            'new_expiry_date': '31/12/2026',
            'opt_in_link': 'https://perizinan.karokab.go.id/whatsapp/opt-in',
            'qr_code_link': 'https://perizinan.karokab.go.id/whatsapp/qr',
        }
        
        try:
            # Get dispatcher
            dispatcher = self.env['sicantik.whatsapp.dispatcher']
            
            # Determine provider (dengan atau tanpa force)
            if self.force_provider_id:
                routing = {
                    'provider': self.force_provider_id,
                    'reason': 'Forced by user (testing)',
                    'use_24h_window': False
                }
                _logger.info(f'🎯 Force using provider: {self.force_provider_id.name}')
            else:
                routing = dispatcher.determine_provider(self.partner_id.id)
                _logger.info(f'🎯 Auto-selected provider: {routing["provider"].name} - {routing["reason"]}')
            
            # Send message
            result = dispatcher.send_template_message(
                template_key=self.template_key,
                partner_id=self.partner_id.id,
                context_values=context_values
            )
            
            # Format result
            if result['success']:
                result_text = f"""✅ TEST BERHASIL

Provider: {result['provider']}
Message ID: {result.get('message_id', 'N/A')}
Penerima: {self.partner_id.name} ({self.partner_id.mobile or self.partner_id.phone})
Template: {self.template_key}

Routing: {routing['reason']}
"""
            else:
                result_text = f"""❌ TEST GAGAL

Provider: {result['provider']}
Error: {result.get('error', 'Unknown error')}
Penerima: {self.partner_id.name} ({self.partner_id.mobile or self.partner_id.phone})
Template: {self.template_key}

Routing: {routing['reason']}
"""
            
            self.test_result = result_text
            
            # Show notification
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Test Selesai',
                    'message': result_text,
                    'type': 'success' if result['success'] else 'danger',
                    'sticky': True,
                }
            }
            
        except Exception as e:
            error_text = f"""❌ TEST ERROR

Error: {str(e)}
Penerima: {self.partner_id.name}
Template: {self.template_key}
"""
            self.test_result = error_text
            
            _logger.error(f'Test failed: {str(e)}', exc_info=True)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Test Error',
                    'message': error_text,
                    'type': 'danger',
                    'sticky': True,
                }
            }

