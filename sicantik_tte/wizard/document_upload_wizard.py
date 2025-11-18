# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
import base64
import logging

_logger = logging.getLogger(__name__)


class DocumentUploadWizard(models.TransientModel):
    """
    Wizard untuk upload dokumen PDF ke MinIO
    """
    _name = 'document.upload.wizard'
    _description = 'Wizard Upload Dokumen'
    
    # Document Selection
    permit_id = fields.Many2one(
        'sicantik.permit',
        string='Pilih Izin',
        required=True,
        domain=[('status', '=', 'active')],
        help='Pilih izin yang akan diupload dokumennya'
    )
    # Related fields untuk display info lengkap
    applicant_name = fields.Char(
        related='permit_id.applicant_name',
        string='Nama Pemohon',
        readonly=True
    )
    permit_number = fields.Char(
        related='permit_id.permit_number',
        string='Nomor Izin',
        readonly=True
    )
    permit_type_id = fields.Many2one(
        related='permit_id.permit_type_id',
        string='Jenis Izin',
        readonly=True
    )
    permit_type_name = fields.Char(
        related='permit_id.permit_type_name',
        string='Nama Jenis Izin',
        readonly=True
    )
    
    # File Upload
    file_data = fields.Binary(
        string='File PDF',
        required=True,
        help='Upload file PDF dokumen izin'
    )
    filename = fields.Char(
        string='Nama File',
        required=True
    )
    
    # Document Info
    document_name = fields.Char(
        string='Nama Dokumen',
        required=True,
        help='Nama dokumen untuk identifikasi'
    )
    notes = fields.Text(
        string='Catatan',
        help='Catatan tambahan untuk dokumen'
    )
    
    # Options
    auto_request_signature = fields.Boolean(
        string='Langsung Minta Tanda Tangan',
        default=False,
        help='Otomatis create workflow tanda tangan setelah upload'
    )
    
    @api.onchange('permit_id')
    def _onchange_permit_id(self):
        """Auto-fill document name based on permit"""
        if self.permit_id:
            self.document_name = f'Dokumen {self.permit_id.permit_type_id.name} - {self.permit_id.permit_number}'
    
    @api.onchange('filename')
    def _onchange_filename(self):
        """Validate PDF file"""
        if self.filename and not self.filename.lower().endswith('.pdf'):
            return {
                'warning': {
                    'title': 'Peringatan',
                    'message': 'File harus berformat PDF'
                }
            }
    
    def action_upload(self):
        """Upload dokumen ke MinIO"""
        self.ensure_one()
        
        # Validate file
        if not self.filename.lower().endswith('.pdf'):
            raise UserError('File harus berformat PDF')
        
        if not self.file_data:
            raise UserError('File belum dipilih')
        
        try:
            # Create document record
            document = self.env['sicantik.document'].create({
                'name': self.document_name,
                'permit_id': self.permit_id.id,
                'notes': self.notes,
                'state': 'draft'
            })
            
            # Decode file data
            file_binary = base64.b64decode(self.file_data)
            
            # Upload to MinIO
            result = document.action_upload_to_minio(
                file_data=file_binary,
                filename=self.filename
            )
            
            if result['success']:
                # Auto request signature if option enabled
                if self.auto_request_signature:
                    document.action_request_signature()
                
                _logger.info(f'Document uploaded successfully: {document.document_number}')
                
                # Return action to open the uploaded document
                return {
                            'type': 'ir.actions.act_window',
                    'name': 'Dokumen Terupload',
                            'res_model': 'sicantik.document',
                            'res_id': document.id,
                            'view_mode': 'form',
                            'target': 'current',
                }
            else:
                # Delete document if upload failed
                document.unlink()
                raise UserError(f'Upload gagal: {result.get("message")}')
                
        except Exception as e:
            _logger.error(f'Error uploading document: {str(e)}')
            raise UserError(f'Error upload dokumen: {str(e)}')
    
    def action_cancel(self):
        """Cancel upload"""
        return {'type': 'ir.actions.act_window_close'}

