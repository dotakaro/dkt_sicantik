# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class SignPassphraseWizard(models.TransientModel):
    """
    Wizard untuk entry passphrase saat signing dokumen
    Security best practice: Passphrase tidak disimpan, hanya di-entry saat signing
    """
    _name = 'sign.passphrase.wizard'
    _description = 'Sign Document Passphrase Wizard'
    
    document_id = fields.Many2one(
        'sicantik.document',
        string='Dokumen',
        required=True,
        readonly=True
    )
    document_name = fields.Char(
        string='Nama Dokumen',
        related='document_id.name',
        readonly=True
    )
    document_number = fields.Char(
        string='Nomor Dokumen',
        related='document_id.document_number',
        readonly=True
    )
    
    passphrase = fields.Char(
        string='Passphrase',
        required=True,
        help='Masukkan passphrase Anda untuk menandatangani dokumen'
    )
    
    confirm_passphrase = fields.Char(
        string='Konfirmasi Passphrase',
        required=True,
        help='Konfirmasi passphrase Anda'
    )
    
    bsre_config_id = fields.Many2one(
        'bsre.config',
        string='Konfigurasi BSRE',
        readonly=True
    )
    signing_identifier = fields.Char(
        string='NIK/Email',
        related='bsre_config_id.signing_identifier',
        readonly=True
    )
    
    def action_sign(self):
        """Execute signing dengan passphrase yang di-entry"""
        self.ensure_one()
        
        # Validate passphrase match
        if self.passphrase != self.confirm_passphrase:
            raise UserError('Passphrase dan konfirmasi tidak cocok. Silakan coba lagi.')
        
        if not self.passphrase:
            raise UserError('Passphrase wajib diisi.')
        
        try:
            # Call document signing dengan passphrase
            result = self.document_id.action_sign_with_bsre_internal(self.passphrase)
            
            if result.get('success'):
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Berhasil',
                        'message': result.get('message', 'Dokumen berhasil ditandatangani'),
                        'type': 'success',
                        'sticky': False,
                        'next': {
                            'type': 'ir.actions.act_window_close',
                        }
                    }
                }
            else:
                raise UserError(result.get('message', 'Signing gagal'))
                
        except Exception as e:
            _logger.error(f'Error signing document: {str(e)}')
            raise UserError(f'Error: {str(e)}')
    
    def action_cancel(self):
        """Cancel signing"""
        return {'type': 'ir.actions.act_window_close'}

