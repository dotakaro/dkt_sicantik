# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request, Response
from odoo.exceptions import UserError, AccessError
import logging
import base64

_logger = logging.getLogger(__name__)


class SicantikTTEController(http.Controller):
    """
    Controller untuk handle download dokumen dari MinIO
    """
    
    @http.route([
        '/web/content/sicantik.document/<int:document_id>/download',
    ], type='http', auth='user', methods=['GET'])
    def download_document(self, document_id, filename=None, **kwargs):
        """
        Download dokumen dari MinIO storage
        
        Args:
            document_id: ID dokumen
            filename: Nama file untuk download (optional)
        
        Returns:
            HTTP Response dengan file data
        """
        try:
            # Get document record
            Document = request.env['sicantik.document'].sudo()
            document = Document.browse(document_id)
            
            if not document.exists():
                return request.not_found()
            
            # Check access rights
            try:
                document.check_access_rights('read')
                document.check_access_rule('read')
            except AccessError:
                return request.render('http_routing.403')
            
            # Check if document has MinIO object
            if not document.minio_object_name:
                _logger.error(f'Document {document_id} does not have MinIO object')
                return Response(
                    'Dokumen belum diupload ke storage',
                    status=404
                )
            
            # Get MinIO connector
            MinioConnector = request.env['minio.connector'].sudo()
            minio_connector = MinioConnector.search([], limit=1)
            
            if not minio_connector:
                _logger.error('MinIO connector not found')
                return Response(
                    'Konfigurasi MinIO tidak ditemukan',
                    status=500
                )
            
            # Download file from MinIO
            _logger.info(f'Downloading document {document_id} from MinIO: {document.minio_object_name}')
            
            download_result = minio_connector.download_file(
                bucket_name=document.minio_bucket,
                object_name=document.minio_object_name
            )
            
            if not download_result.get('success'):
                error_msg = download_result.get('message', 'Unknown error')
                _logger.error(f'Failed to download from MinIO: {error_msg}')
                return Response(
                    f'Gagal download dari MinIO: {error_msg}',
                    status=500
                )
            
            # Get file data
            file_data = download_result['data']
            
            # Determine filename
            if not filename:
                filename = document.original_filename or 'document.pdf'
            
            # Prepare response headers
            headers = [
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'attachment; filename="{filename}"'),
                ('Content-Length', len(file_data)),
            ]
            
            _logger.info(f'Document {document_id} downloaded successfully: {filename} ({len(file_data)} bytes)')
            
            # Return file as HTTP response
            return Response(
                file_data,
                headers=headers,
                status=200
            )
            
        except Exception as e:
            _logger.error(f'Error downloading document {document_id}: {str(e)}', exc_info=True)
            return Response(
                f'Error download dokumen: {str(e)}',
                status=500
            )
    
    @http.route([
        '/sicantik/tte/verify/<string:document_number>',
        '/verify/<string:document_number>',
    ], type='http', auth='public', website=True, methods=['GET'])
    def verify_document(self, document_number, **kwargs):
        """
        Public endpoint untuk verifikasi dokumen
        
        Args:
            document_number: Nomor dokumen
        
        Returns:
            Halaman verifikasi dokumen
        """
        try:
            # Get document
            Document = request.env['sicantik.document'].sudo()
            document = Document.search([
                ('document_number', '=', document_number),
                ('state', 'in', ['signed', 'verified'])
            ], limit=1)
            
            if not document:
                return request.render('sicantik_tte.verification_not_found', {
                    'document_number': document_number
                })
            
            # Update verification counter
            document.write({
                'verification_count': document.verification_count + 1,
                'last_verified_date': http.request.env['ir.fields'].datetime.now()
            })
            
            # Render verification page
            return request.render('sicantik_tte.verification_page', {
                'document': document,
            })
            
        except Exception as e:
            _logger.error(f'Error verifying document {document_number}: {str(e)}')
            return request.render('sicantik_tte.verification_error', {
                'error': str(e)
            })

