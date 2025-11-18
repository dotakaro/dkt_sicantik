# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ExportPhoneNumbersWizard(models.TransientModel):
    """
    Wizard untuk export nomor HP ke CSV untuk di-upload ke Meta Business Manager
    """
    _name = 'whatsapp.export.phone.numbers.wizard'
    _description = 'Export Phone Numbers for Meta Approval'
    
    wa_account_id = fields.Many2one(
        'whatsapp.account',
        string='WhatsApp Account',
        required=True,
        help='WhatsApp Business Account untuk export nomor'
    )
    
    limit = fields.Integer(
        string='Limit',
        default=1000,
        help='Maximum number of phone numbers to export (0 = all)'
    )
    
    include_only_with_permits = fields.Boolean(
        string='Only Partners with Permits',
        default=True,
        help='Hanya export nomor dari partner yang memiliki permit'
    )
    
    @api.model
    def default_get(self, fields_list):
        """Set default WhatsApp Account"""
        res = super().default_get(fields_list)
        
        # Cari WhatsApp Account aktif
        wa_account = self.env['whatsapp.account'].search([
            ('active', '=', True)
        ], limit=1)
        
        if wa_account:
            res['wa_account_id'] = wa_account.id
        
        return res
    
    def action_export_phone_numbers(self):
        """
        Export nomor HP ke CSV untuk di-upload ke Meta Business Manager
        """
        self.ensure_one()
        
        if not self.wa_account_id:
            raise UserError(_('Pilih WhatsApp Account terlebih dahulu'))
        
        # Export nomor
        opt_in_manager = self.env['whatsapp.opt.in.manager']
        export_result = opt_in_manager.export_phone_numbers_for_meta_approval(
            wa_account_id=self.wa_account_id.id,
            limit=self.limit if self.limit > 0 else None
        )
        
        # Download file
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/whatsapp.opt.in.manager/{export_result["filename"]}?download=true&file_content={export_result["file_content"]}',
            'target': 'self',
        }
    
    def action_download_csv(self):
        """
        Download CSV file dengan nomor HP
        """
        self.ensure_one()
        
        if not self.wa_account_id:
            raise UserError(_('Pilih WhatsApp Account terlebih dahulu'))
        
        # Export nomor
        opt_in_manager = self.env['whatsapp.opt.in.manager']
        export_result = opt_in_manager.export_phone_numbers_for_meta_approval(
            wa_account_id=self.wa_account_id.id,
            limit=self.limit if self.limit > 0 else None
        )
        
        # Create attachment
        attachment = self.env['ir.attachment'].sudo().create({
            'name': export_result['filename'],
            'type': 'binary',
            'datas': export_result['file_content'],
            'mimetype': 'text/csv',
            'res_model': self._name,
            'res_id': self.id,
        })
        
        _logger.info(f'✅ CSV file created: {export_result["filename"]} with {export_result["total_numbers"]} numbers')
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=1',
            'target': 'self',
        }

