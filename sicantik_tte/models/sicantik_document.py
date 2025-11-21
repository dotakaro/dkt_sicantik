# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import base64
import hashlib
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class SicantikDocument(models.Model):
    """
    Model untuk menyimpan dokumen perizinan yang akan ditandatangani
    """
    _name = 'sicantik.document'
    _description = 'Dokumen Perizinan SICANTIK'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'document_number'
    
    # Document Information
    document_number = fields.Char(
        string='Nomor Dokumen',
        required=True,
        copy=False,
        readonly=True,
        default='New',
        tracking=True
    )
    name = fields.Char(
        string='Nama Dokumen',
        required=True,
        tracking=True
    )
    permit_id = fields.Many2one(
        'sicantik.permit',
        string='Izin Terkait',
        required=True,
        ondelete='restrict',
        tracking=True
    )
    permit_number = fields.Char(
        related='permit_id.permit_number',
        string='Nomor Izin',
        store=True
    )
    permit_type_id = fields.Many2one(
        related='permit_id.permit_type_id',
        string='Jenis Izin',
        store=True
    )
    
    # File Information
    original_filename = fields.Char(
        string='Nama File Asli',
        readonly=True
    )
    file_size = fields.Integer(
        string='Ukuran File (bytes)',
        readonly=True
    )
    file_hash = fields.Char(
        string='Hash File (SHA256)',
        readonly=True,
        help='Hash untuk verifikasi integritas dokumen'
    )
    
    # MinIO Storage
    minio_bucket = fields.Char(
        string='MinIO Bucket',
        readonly=True,
        default='sicantik-documents'
    )
    minio_object_name = fields.Char(
        string='MinIO Object Name',
        readonly=True,
        help='Path file di MinIO storage'
    )
    minio_url = fields.Char(
        string='MinIO URL',
        readonly=True,
        compute='_compute_minio_url',
        store=True
    )
    
    # Document Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('uploaded', 'Terupload'),
        ('pending_signature', 'Menunggu Tanda Tangan'),
        ('signed', 'Tertandatangani'),
        ('verified', 'Terverifikasi'),
        ('rejected', 'Ditolak'),
        ('cancelled', 'Dibatalkan'),
    ], string='Status', default='draft', required=True, tracking=True)
    
    # Signature Information
    signature_date = fields.Datetime(
        string='Tanggal Tanda Tangan',
        readonly=True,
        tracking=True
    )
    signer_id = fields.Many2one(
        'res.users',
        string='Penandatangan',
        readonly=True,
        tracking=True
    )
    signature_method = fields.Selection([
        ('bsre', 'BSRE TTE'),
        ('manual', 'Manual Upload'),
    ], string='Metode Tanda Tangan', readonly=True)
    
    # BSRE Information
    bsre_request_id = fields.Char(
        string='BSRE Request ID',
        readonly=True
    )
    bsre_signature_id = fields.Char(
        string='BSRE Signature ID',
        readonly=True
    )
    bsre_certificate = fields.Text(
        string='BSRE Certificate',
        readonly=True
    )
    
    # QR Code
    qr_code_data = fields.Text(
        string='QR Code Data',
        readonly=True,
        help='Data yang diencode dalam QR code'
    )
    qr_code_image = fields.Binary(
        string='QR Code Image',
        readonly=True,
        attachment=True
    )
    qr_code_embedded = fields.Boolean(
        string='QR Code Sudah Diembed',
        default=False,
        readonly=True
    )
    
    # Verification
    verification_url = fields.Char(
        string='URL Verifikasi',
        compute='_compute_verification_url',
        store=True
    )
    verification_count = fields.Integer(
        string='Jumlah Verifikasi',
        default=0,
        readonly=True
    )
    last_verified_date = fields.Datetime(
        string='Terakhir Diverifikasi',
        readonly=True
    )
    
    # Metadata
    uploaded_by = fields.Many2one(
        'res.users',
        string='Diupload Oleh',
        default=lambda self: self.env.user,
        readonly=True
    )
    upload_date = fields.Datetime(
        string='Tanggal Upload',
        default=fields.Datetime.now,
        readonly=True
    )
    notes = fields.Text(
        string='Catatan'
    )
    
    # Phone field for WhatsApp notifications
    mobile = fields.Char(
        string='Mobile',
        compute='_compute_mobile',
        readonly=True,
        store=False,
        help='Mobile number from signer or creator (for WhatsApp notifications)'
    )
    
    # Computed Fields
    can_sign = fields.Boolean(
        string='Dapat Ditandatangani',
        compute='_compute_can_sign'
    )
    can_download = fields.Boolean(
        string='Dapat Diunduh',
        compute='_compute_can_download'
    )
    
    @api.depends('signer_id', 'create_uid')
    def _compute_mobile(self):
        """Compute mobile number from signer or creator using safe accessor"""
        for record in self:
            mobile_number = False
            # Prioritize signer_id, fallback to create_uid
            if record.signer_id:
                # Try signer's partner first, then signer itself (if signer is a user)
                if hasattr(record.signer_id, 'partner_id') and record.signer_id.partner_id:
                    mobile_number = record.signer_id.partner_id._get_mobile_or_phone()
                elif hasattr(record.signer_id, '_get_mobile_or_phone'):
                    mobile_number = record.signer_id._get_mobile_or_phone()
            elif record.create_uid:
                # create_uid is res.users, try partner_id first
                if record.create_uid.partner_id:
                    mobile_number = record.create_uid.partner_id._get_mobile_or_phone()
                elif hasattr(record.create_uid, '_get_mobile_or_phone'):
                    mobile_number = record.create_uid._get_mobile_or_phone()
            record.mobile = mobile_number
    
    @api.depends('minio_bucket', 'minio_object_name')
    def _compute_minio_url(self):
        """Compute MinIO URL untuk download"""
        for record in self:
            if record.minio_bucket and record.minio_object_name:
                # Get MinIO config from environment or config
                minio_endpoint = self.env['ir.config_parameter'].sudo().get_param(
                    'sicantik_tte.minio_endpoint', 'localhost:9000'
                )
                record.minio_url = f'http://{minio_endpoint}/{record.minio_bucket}/{record.minio_object_name}'
            else:
                record.minio_url = False
    
    @api.depends('document_number', 'state')
    def _compute_verification_url(self):
        """Compute URL untuk verifikasi publik"""
        for record in self:
            if record.document_number and record.document_number != 'New' and record.state in ['signed', 'verified']:
                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                if not base_url:
                    base_url = 'http://localhost:8060'  # Fallback
                record.verification_url = f'{base_url}/sicantik/tte/verify/{record.document_number}'
            else:
                record.verification_url = False
    
    @api.depends('state', 'minio_object_name')
    def _compute_can_sign(self):
        """Check apakah dokumen dapat ditandatangani"""
        for record in self:
            record.can_sign = (
                record.state == 'pending_signature' and
                record.minio_object_name and
                self.env.user.has_group('base.group_system')
            )
    
    @api.depends('state', 'minio_object_name')
    def _compute_can_download(self):
        """Check apakah dokumen dapat diunduh"""
        for record in self:
            record.can_download = (
                record.minio_object_name and
                record.state in ['uploaded', 'pending_signature', 'signed', 'verified']
            )
    
    @api.model
    def create(self, vals):
        """Override create untuk generate document number"""
        if vals.get('document_number', 'New') == 'New':
            vals['document_number'] = self.env['ir.sequence'].next_by_code('sicantik.document') or 'New'
        return super().create(vals)
    
    def action_upload_to_minio(self, file_data, filename):
        """
        Upload file ke MinIO storage
        
        Args:
            file_data (bytes): Binary data file
            filename (str): Nama file
        
        Returns:
            dict: Result with success status and message
        """
        self.ensure_one()
        
        try:
            # Get MinIO connector (prioritize active one)
            minio_connector = self.env['minio.connector'].search([
                ('active', '=', True)
            ], limit=1)
            if not minio_connector:
                # Fallback to any connector if no active one
                minio_connector = self.env['minio.connector'].search([], limit=1)
            if not minio_connector:
                raise UserError('Konfigurasi MinIO tidak ditemukan. Silakan buat konfigurasi MinIO terlebih dahulu.')
            
            # Determine bucket name
            bucket_name = self.minio_bucket or minio_connector.default_bucket or 'sicantik-documents'
            if not bucket_name:
                raise UserError('Nama bucket tidak ditemukan. Silakan set bucket name di dokumen atau konfigurasi MinIO.')
            
            # Generate unique object name
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            object_name = f'{self.permit_id.permit_number}/{timestamp}_{filename}'
            
            # Calculate file hash
            file_hash = hashlib.sha256(file_data).hexdigest()
            
            _logger.info(f'Uploading document: bucket={bucket_name}, object={object_name}, size={len(file_data)} bytes')
            
            # Upload to MinIO
            result = minio_connector.upload_file(
                bucket_name=bucket_name,
                object_name=object_name,
                file_data=file_data,
                content_type='application/pdf'
            )
            
            if result['success']:
                # Update record
                self.write({
                    'original_filename': filename,
                    'file_size': len(file_data),
                    'file_hash': file_hash,
                    'minio_bucket': bucket_name,  # Ensure bucket name is saved
                    'minio_object_name': object_name,
                    'state': 'uploaded',
                    'upload_date': fields.Datetime.now()
                })
                
                _logger.info(f'Document {self.document_number} uploaded to MinIO: {object_name}')
                
                return {
                    'success': True,
                    'message': f'Dokumen berhasil diupload ke MinIO',
                    'object_name': object_name
                }
            else:
                raise UserError(f'Upload gagal: {result.get("message")}')
                
        except Exception as e:
            _logger.error(f'Error uploading document {self.document_number}: {str(e)}')
            raise UserError(f'Error upload dokumen: {str(e)}')
    
    def action_download_from_minio(self):
        """Download file dari MinIO storage"""
        self.ensure_one()
        
        if not self.minio_object_name:
            raise UserError('Dokumen belum diupload ke MinIO')
        
        try:
            # Get MinIO connector
            minio_connector = self.env['minio.connector'].search([], limit=1)
            if not minio_connector:
                raise UserError('Konfigurasi MinIO tidak ditemukan')
            
            # Download from MinIO
            result = minio_connector.download_file(
                bucket_name=self.minio_bucket,
                object_name=self.minio_object_name
            )
            
            if result['success']:
                # Return file as attachment
                return {
                    'type': 'ir.actions.act_url',
                    'url': f'/web/content/sicantik.document/{self.id}/download?filename={self.original_filename}',
                    'target': 'self',
                }
            else:
                raise UserError(f'Download gagal: {result.get("message")}')
                
        except Exception as e:
            _logger.error(f'Error downloading document {self.document_number}: {str(e)}')
            raise UserError(f'Error download dokumen: {str(e)}')
    
    def action_request_signature(self):
        """Request tanda tangan digital via BSRE"""
        self.ensure_one()
        
        if self.state != 'uploaded':
            raise UserError('Dokumen harus dalam status "Terupload" untuk diminta tanda tangan')
        
        # Create signature workflow
        workflow = self.env['signature.workflow'].create({
            'document_id': self.id,
            'state': 'pending',
        })
        
        # Update document state
        self.write({'state': 'pending_signature'})
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Workflow Tanda Tangan',
            'res_model': 'signature.workflow',
            'res_id': workflow.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_sign_with_bsre(self):
        """Open wizard untuk entry passphrase dan sign dokumen dengan BSRE"""
        self.ensure_one()
        
        if self.state != 'pending_signature':
            raise UserError('Dokumen harus dalam status "Menunggu Tanda Tangan"')
        
        # Get BSRE configuration
        bsre_config = self.env['bsre.config'].search([('active', '=', True)], limit=1)
        if not bsre_config:
            raise UserError('Konfigurasi BSRE tidak ditemukan')
        
        # Open passphrase wizard
        return {
            'name': 'Tandatangani Dokumen',
            'type': 'ir.actions.act_window',
            'res_model': 'sign.passphrase.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_document_id': self.id,
                'default_bsre_config_id': bsre_config.id,
            }
        }
    
    def action_sign_with_bsre_internal(self, passphrase):
        """
        Internal method untuk sign dokumen dengan BSRE (dipanggil dari wizard)
        
        Args:
            passphrase (str): Passphrase dari user untuk signing
        """
        self.ensure_one()
        
        if self.state != 'pending_signature':
            raise UserError('Dokumen harus dalam status "Menunggu Tanda Tangan"')
        
        try:
            # Get BSRE connector
            bsre_config = self.env['bsre.config'].search([('active', '=', True)], limit=1)
            if not bsre_config:
                raise UserError('Konfigurasi BSRE tidak ditemukan')
            
            # Download file from MinIO
            minio_connector = self.env['minio.connector'].search([], limit=1)
            download_result = minio_connector.download_file(
                bucket_name=self.minio_bucket,
                object_name=self.minio_object_name
            )
            
            if not download_result['success']:
                raise UserError('Gagal download dokumen dari MinIO')
            
            file_data = download_result['data']
            
            # Sign with BSRE (dengan passphrase dari user)
            sign_result = bsre_config.sign_document(
                document_data=file_data,
                document_name=self.original_filename,
                passphrase=passphrase  # Passphrase dari wizard
            )
            
            if sign_result['success']:
                # Upload signed document back to MinIO
                signed_object_name = self.minio_object_name.replace('.pdf', '_signed.pdf')
                upload_result = minio_connector.upload_file(
                    bucket_name=self.minio_bucket,
                    object_name=signed_object_name,
                    file_data=sign_result['signed_data'],
                    content_type='application/pdf'
                )
                
                if upload_result['success']:
                    # Update record with signed document info
                    self.write({
                        'state': 'signed',
                        'signature_date': fields.Datetime.now(),
                        'signer_id': self.env.user.id,
                        'signature_method': 'bsre',
                        'bsre_request_id': sign_result.get('request_id'),
                        'bsre_signature_id': sign_result.get('signature_id'),
                        'bsre_certificate': sign_result.get('certificate'),
                        'minio_object_name': signed_object_name,
                    })
                    
                    # Generate QR Code
                    self._generate_qr_code()
                    
                    # Embed QR Code ke PDF
                    try:
                        self.action_embed_qr_code()
                        _logger.info(f'QR code embedded for document {self.document_number}')
                    except Exception as qr_error:
                        _logger.error(f'Failed to embed QR code: {qr_error}')
                        # Continue even if QR embedding fails
                    
                    _logger.info(f'Document {self.document_number} signed with BSRE')
                    
                    return {
                        'success': True,
                        'message': f'Dokumen {self.document_number} berhasil ditandatangani dengan BSRE dan QR code'
                    }
                else:
                    return {
                        'success': False,
                        'message': 'Gagal upload dokumen tertandatangani ke MinIO'
                    }
            else:
                return {
                    'success': False,
                    'message': f'Gagal tanda tangan BSRE: {sign_result.get("message")}'
                }
                
        except Exception as e:
            _logger.error(f'Error signing document {self.document_number}: {str(e)}')
            return {
                'success': False,
                'message': f'Error tanda tangan dokumen: {str(e)}'
            }
    
    def _generate_qr_code(self):
        """Generate QR code untuk verifikasi dokumen"""
        self.ensure_one()
        
        try:
            import qrcode
            from io import BytesIO
            
            # Get base URL
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            
            # QR code hanya berisi URL verifikasi untuk auto-redirect saat di-scan
            verification_url = f'{base_url}/sicantik/tte/verify/{self.document_number}'
            
            # Generate QR code dengan URL langsung (tidak JSON)
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=4,
            )
            qr.add_data(verification_url)
            qr.make(fit=True)
            
            # Create image
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to binary
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            qr_image_data = base64.b64encode(buffer.getvalue())
            
            # Update record
            self.write({
                'qr_code_data': verification_url,  # Simpan URL untuk reference
                'qr_code_image': qr_image_data,
            })
            
            _logger.info(f'QR code generated for document {self.document_number}: {verification_url}')
            
        except Exception as e:
            _logger.error(f'Error generating QR code: {str(e)}')
            # Don't raise error, just log it
    
    def action_embed_qr_code(self):
        """
        Embed QR code ke dalam PDF signed document
        QR Code akan ditambahkan di pojok kanan bawah setiap halaman
        """
        self.ensure_one()
        
        if not self.qr_code_image:
            raise UserError('QR code belum digenerate')
        
        if self.qr_code_embedded:
            _logger.info(f'QR code already embedded for document {self.document_number}')
            return True
        
        try:
            from PyPDF2 import PdfReader, PdfWriter
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.units import inch
            from reportlab.lib.utils import ImageReader
            from io import BytesIO
            from PIL import Image
            
            # Get MinIO connector
            minio_connector = self.env['minio.connector'].search([], limit=1)
            if not minio_connector:
                raise UserError('Konfigurasi MinIO tidak ditemukan')
            
            # Download signed PDF from MinIO
            download_result = minio_connector.download_file(
                bucket_name=self.minio_bucket,
                object_name=self.minio_object_name
            )
            
            if not download_result['success']:
                raise UserError('Gagal download dokumen dari MinIO')
            
            pdf_data = download_result['data']
            
            # Decode QR code image
            qr_image_bytes = base64.b64decode(self.qr_code_image)
            qr_image = Image.open(BytesIO(qr_image_bytes))
            
            # Convert PIL Image to ImageReader for reportlab
            qr_buffer = BytesIO()
            qr_image.save(qr_buffer, format='PNG')
            qr_buffer.seek(0)
            qr_img_reader = ImageReader(qr_buffer)
            
            # Read existing PDF
            existing_pdf = PdfReader(BytesIO(pdf_data))
            output = PdfWriter()
            
            # Process each page
            for page_num in range(len(existing_pdf.pages)):
                page = existing_pdf.pages[page_num]
                
                # Get page dimensions
                page_width = float(page.mediabox.width)
                page_height = float(page.mediabox.height)
                
                # Create overlay with QR code
                packet = BytesIO()
                can = canvas.Canvas(packet, pagesize=(page_width, page_height))
                
                # QR code size and position (BOTTOM LEFT to avoid BSRE signature)
                qr_size = 1.2 * inch  # 1.2 inch = ~3 cm
                margin = 0.3 * inch   # 0.3 inch margin from edges
                
                # Position: BOTTOM LEFT corner (BSRE signature di kanan)
                x_position = margin
                y_position = margin
                
                # Draw QR code
                can.drawImage(
                    qr_img_reader,
                    x_position,
                    y_position,
                    width=qr_size,
                    height=qr_size,
                    preserveAspectRatio=True,
                    mask='auto'
                )
                
                # Add verification text below QR code
                can.setFont("Helvetica", 7)
                can.setFillColorRGB(0, 0, 0)
                text_y = y_position - 0.15 * inch
                can.drawString(
                    x_position,
                    text_y,
                    f"Scan untuk verifikasi"
                )
                can.drawString(
                    x_position,
                    text_y - 0.12 * inch,
                    f"Doc: {self.document_number}"
                )
                
                can.save()
                
                # Merge overlay with page
                packet.seek(0)
                overlay_pdf = PdfReader(packet)
                page.merge_page(overlay_pdf.pages[0])
                
                # Add to output
                output.add_page(page)
            
            # Write output PDF
            output_buffer = BytesIO()
            output.write(output_buffer)
            output_buffer.seek(0)
            final_pdf_data = output_buffer.read()
            
            # Upload back to MinIO (replace the signed file)
            upload_result = minio_connector.upload_file(
                bucket_name=self.minio_bucket,
                object_name=self.minio_object_name,
                file_data=final_pdf_data,
                content_type='application/pdf'
            )
            
            if upload_result['success']:
                # Update record
                self.write({
                    'qr_code_embedded': True,
                    'file_size': len(final_pdf_data)
                })
                
                _logger.info(f'QR code embedded successfully for document {self.document_number}')
                
                return True
            else:
                raise UserError('Gagal upload dokumen dengan QR code ke MinIO')
            
        except Exception as e:
            _logger.error(f'Error embedding QR code: {str(e)}', exc_info=True)
            raise UserError(f'Error embed QR code: {str(e)}')
    
    def action_open_upload_wizard(self):
        """Buka wizard upload dokumen baru"""
        # Bisa dipanggil dari form view yang sudah ada record atau dari action
        return {
            'type': 'ir.actions.act_window',
            'name': 'Upload Dokumen',
            'res_model': 'document.upload.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {}
        }
    
    def action_cancel(self):
        """Cancel dokumen"""
        self.ensure_one()
        
        if self.state == 'signed':
            raise UserError('Dokumen yang sudah ditandatangani tidak dapat dibatalkan')
        
        self.write({'state': 'cancelled'})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Dibatalkan',
                'message': 'Dokumen telah dibatalkan',
                'type': 'warning',
                'sticky': False,
            }
        }

