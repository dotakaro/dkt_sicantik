# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class BatchSignWizard(models.TransientModel):
    """
    Wizard untuk batch signing multiple documents
    """
    _name = 'batch.sign.wizard'
    _description = 'Wizard Batch Sign Dokumen'
    
    document_ids = fields.Many2many(
        'sicantik.document',
        string='Dokumen',
        required=True,
        domain=[('state', '=', 'pending_signature')],
        help='Pilih dokumen yang akan ditandatangani'
    )
    document_count = fields.Integer(
        string='Jumlah Dokumen',
        compute='_compute_document_count'
    )
    
    # Signing Options
    signature_notes = fields.Text(
        string='Catatan Tanda Tangan',
        help='Catatan yang akan ditambahkan ke semua dokumen'
    )
    
    @api.depends('document_ids')
    def _compute_document_count(self):
        for wizard in self:
            wizard.document_count = len(wizard.document_ids)
    
    def action_sign_batch(self):
        """Sign multiple documents"""
        self.ensure_one()
        
        if not self.document_ids:
            raise UserError('Tidak ada dokumen yang dipilih')
        
        success_count = 0
        failed_count = 0
        failed_docs = []
        
        for document in self.document_ids:
            try:
                # Sign document
                document.action_sign_with_bsre()
                success_count += 1
                
                _logger.info(f'Document signed: {document.document_number}')
                
            except Exception as e:
                failed_count += 1
                failed_docs.append(f'{document.document_number}: {str(e)}')
                _logger.error(f'Error signing document {document.document_number}: {str(e)}')
        
        # Prepare result message
        if failed_count == 0:
            message = f'Semua {success_count} dokumen berhasil ditandatangani'
            msg_type = 'success'
        elif success_count == 0:
            message = f'Semua {failed_count} dokumen gagal ditandatangani'
            msg_type = 'danger'
        else:
            message = f'{success_count} dokumen berhasil, {failed_count} dokumen gagal ditandatangani'
            msg_type = 'warning'
        
        # Show failed documents if any
        if failed_docs:
            message += '\n\nGagal:\n' + '\n'.join(failed_docs)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Batch Signing Selesai',
                'message': message,
                'type': msg_type,
                'sticky': True if failed_count > 0 else False,
            }
        }
    
    def action_cancel(self):
        """Cancel batch signing"""
        return {'type': 'ir.actions.act_window_close'}

