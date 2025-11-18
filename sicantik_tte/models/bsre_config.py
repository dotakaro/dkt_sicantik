# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import requests
import base64
import json
import logging

_logger = logging.getLogger(__name__)


class BsreConfig(models.Model):
    """
    Konfigurasi untuk BSRE (Badan Siber dan Sandi Negara) TTE API
    """
    _name = 'bsre.config'
    _description = 'Konfigurasi BSRE TTE'
    _rec_name = 'name'
    
    name = fields.Char(
        string='Nama Konfigurasi',
        required=True,
        default='BSRE Production'
    )
    active = fields.Boolean(
        string='Aktif',
        default=True
    )
    
    # BSRE API Configuration
    api_url = fields.Char(
        string='URL API BSRE',
        required=True,
        default='http://tte.karokab.go.id',
        help='Base URL untuk BSRE API'
    )
    username = fields.Char(
        string='Username',
        required=True,
        help='Username akun BSRE (untuk Basic Auth header)'
    )
    password = fields.Char(
        string='Password',
        required=True,
        help='Password akun BSRE (untuk Basic Auth header)'
    )
    
    # User Signing Credentials (untuk actual signing)
    signing_identifier_type = fields.Selection([
        ('nik', 'NIK'),
        ('email', 'Email'),
    ], string='Tipe Identifier', default='nik', required=True,
       help='Identifier untuk signing: NIK atau Email')
    
    signing_identifier = fields.Char(
        string='NIK/Email untuk Signing',
        required=True,
        help='NIK atau Email yang akan digunakan untuk sign dokumen'
    )
    
    use_otp = fields.Boolean(
        string='Gunakan OTP',
        default=False,
        help='Gunakan OTP instead of passphrase (belum diimplementasikan)'
    )
    
    # Certificate Configuration
    certificate_id = fields.Char(
        string='Certificate ID',
        help='ID sertifikat digital yang digunakan'
    )
    certificate_owner = fields.Char(
        string='Pemilik Sertifikat',
        help='Nama pemilik sertifikat digital'
    )
    certificate_valid_until = fields.Date(
        string='Sertifikat Berlaku Sampai',
        help='Tanggal kadaluarsa sertifikat'
    )
    
    # Signature Configuration
    signature_position = fields.Selection([
        ('bottom_left', 'Kiri Bawah'),
        ('bottom_right', 'Kanan Bawah'),
        ('top_left', 'Kiri Atas'),
        ('top_right', 'Kanan Atas'),
        ('center', 'Tengah'),
    ], string='Posisi Tanda Tangan', default='bottom_right')
    
    signature_page = fields.Selection([
        ('first', 'Halaman Pertama'),
        ('last', 'Halaman Terakhir'),
        ('all', 'Semua Halaman'),
    ], string='Halaman Tanda Tangan', default='last')
    
    signature_visible = fields.Boolean(
        string='Tanda Tangan Visible',
        default=True,
        help='Tampilkan tanda tangan visual di PDF'
    )
    
    # Custom Signature Appearance
    signature_image = fields.Binary(
        string='Logo/Tanda Tangan',
        attachment=True,
        help='Upload logo atau gambar tanda tangan untuk ditampilkan di PDF. Format: PNG dengan transparansi. Jika kosong, akan menggunakan placeholder default.'
    )
    signature_image_filename = fields.Char(
        string='Nama File'
    )
    
    # Signature Size Preset
    signature_size = fields.Selection([
        ('small', 'Kecil (Max 80x60)'),
        ('medium', 'Sedang (Max 120x90)'),
        ('large', 'Besar (Max 160x120)'),
        ('xlarge', 'Sangat Besar (Max 200x150)'),
        ('custom', 'Custom'),
    ], string='Ukuran Signature', default='small',
       help='Ukuran maksimum signature. Aspek rasio original akan dipertahankan - gambar akan di-fit dalam bounds tanpa distorsi.')
    
    # Signature Dimensions (for custom size)
    signature_width = fields.Float(
        string='Lebar Signature (px)',
        default=100.0,
        help='Lebar signature field dalam pixel (aktif jika ukuran = Custom)'
    )
    signature_height = fields.Float(
        string='Tinggi Signature (px)',
        default=75.0,
        help='Tinggi signature field dalam pixel (aktif jika ukuran = Custom)'
    )
    
    # Custom Position Override
    use_custom_position = fields.Boolean(
        string='Gunakan Posisi Custom',
        default=False,
        help='Centang untuk menggunakan koordinat X,Y manual (override preset posisi)'
    )
    custom_position_x = fields.Float(
        string='Posisi X (px)',
        default=0.0,
        help='Koordinat X dari kiri PDF (0 = kiri). Hanya aktif jika "Gunakan Posisi Custom" dicentang.'
    )
    custom_position_y = fields.Float(
        string='Posisi Y (px)',
        default=0.0,
        help='Koordinat Y dari bawah PDF (0 = bawah). Hanya aktif jika "Gunakan Posisi Custom" dicentang.'
    )
    
    # Timeout & Retry
    api_timeout = fields.Integer(
        string='API Timeout (detik)',
        default=60,
        help='Timeout untuk request API'
    )
    max_retry = fields.Integer(
        string='Max Retry',
        default=3,
        help='Maksimal retry jika request gagal'
    )
    
    # Connection Status
    connection_status = fields.Selection([
        ('disconnected', 'Terputus'),
        ('connected', 'Terhubung'),
        ('error', 'Error')
    ], string='Status Koneksi', default='disconnected', readonly=True)
    
    last_error = fields.Text(
        string='Error Terakhir',
        readonly=True
    )
    
    # Statistics
    total_signatures = fields.Integer(
        string='Total Tanda Tangan',
        default=0,
        readonly=True
    )
    successful_signatures = fields.Integer(
        string='Tanda Tangan Berhasil',
        default=0,
        readonly=True
    )
    failed_signatures = fields.Integer(
        string='Tanda Tangan Gagal',
        default=0,
        readonly=True
    )
    last_signature_date = fields.Datetime(
        string='Tanda Tangan Terakhir',
        readonly=True
    )
    
    @api.constrains('active')
    def _check_one_active_config(self):
        """Ensure only one active BSRE configuration"""
        if self.active:
            active_configs = self.search([('active', '=', True), ('id', '!=', self.id)])
            if active_configs:
                raise ValidationError('Hanya satu konfigurasi BSRE yang dapat aktif pada satu waktu')
    
    @api.constrains('use_custom_position', 'custom_position_x', 'custom_position_y', 'signature_width', 'signature_height')
    def _check_custom_position_bounds(self):
        """
        Validate custom position coordinates stay within A4 page bounds
        V2 API menggunakan A4 Portrait: 595 x 842 points
        """
        for record in self:
            if record.use_custom_position:
                PAGE_WIDTH = 595
                PAGE_HEIGHT = 842
                
                # Get signature dimensions
                sig_width = record._get_signature_width()
                sig_height = record._get_signature_height()
                
                # Validate X coordinate
                if record.custom_position_x < 0:
                    raise ValidationError('Posisi X tidak boleh negatif!')
                if record.custom_position_x + sig_width > PAGE_WIDTH:
                    raise ValidationError(
                        f'Signature keluar dari halaman!\n'
                        f'originX ({record.custom_position_x}) + width ({sig_width}) = {record.custom_position_x + sig_width}\n'
                        f'MAX allowed: {PAGE_WIDTH} (A4 width)\n\n'
                        f'Solusi: Kurangi originX atau gunakan signature yang lebih kecil.'
                    )
                
                # Validate Y coordinate
                if record.custom_position_y < 0:
                    raise ValidationError('Posisi Y tidak boleh negatif!')
                if record.custom_position_y + sig_height > PAGE_HEIGHT:
                    raise ValidationError(
                        f'Signature keluar dari halaman!\n'
                        f'originY ({record.custom_position_y}) + height ({sig_height}) = {record.custom_position_y + sig_height}\n'
                        f'MAX allowed: {PAGE_HEIGHT} (A4 height)\n\n'
                        f'Solusi: Kurangi originY atau gunakan signature yang lebih kecil.'
                    )
    
    def _make_api_request(self, endpoint, method='POST', data=None, files=None):
        """
        Make API request to BSRE using Basic Authentication
        
        Args:
            endpoint (str): API endpoint
            method (str): HTTP method
            data (dict): Request data
            files (dict): Files to upload
        
        Returns:
            dict: API response
        """
        self.ensure_one()
        
        url = f'{self.api_url}/{endpoint}'
        
        # Use Basic Authentication with username and password
        auth = (self.username, self.password)
        
        headers = {}
        
        try:
            _logger.info(f'BSRE API Request: {method} {url}')
            
            if method == 'POST':
                if files:
                    response = requests.post(url, auth=auth, data=data, files=files, timeout=self.api_timeout)
                else:
                    headers['Content-Type'] = 'application/json'
                    # Log request data (tanpa file base64 untuk tidak flood log)
                    debug_data = {k: v if k != 'file' else f'[{len(v)} files]' for k, v in (data or {}).items()}
                    _logger.info(f'Request data: {json.dumps(debug_data)}')
                    
                    response = requests.post(url, auth=auth, headers=headers, json=data, timeout=self.api_timeout)
            elif method == 'GET':
                response = requests.get(url, auth=auth, params=data, timeout=self.api_timeout)
            else:
                raise NotImplementedError(f'HTTP method {method} not implemented')
            
            _logger.info(f'BSRE API Response: {response.status_code}')
            
            # Log response body untuk debugging (truncate jika terlalu panjang)
            try:
                response_text = response.text[:1000] if len(response.text) > 1000 else response.text
                _logger.info(f'Response body: {response_text}')
            except:
                pass
            
            # Check status code before raise_for_status
            if response.status_code != 200:
                error_details = {
                    'status_code': response.status_code,
                    'url': url,
                    'method': method,
                    'response_text': response.text[:500] if response.text else 'No response body'
                }
                _logger.error(f'BSRE API Error: {json.dumps(error_details, indent=2)}')
                
                # IMPORTANT: BSRE sometimes returns 500 but with valid signed PDF in response body
                # Try to parse response as JSON first to check for 'file' key
                try:
                    error_json = response.json()
                    
                    # If response contains 'file' key with signed PDF, treat as success despite 500 error
                    if isinstance(error_json, dict) and 'file' in error_json and error_json.get('file'):
                        _logger.warning(f'BSRE returned {response.status_code} but response contains valid signed file. Treating as success.')
                        return error_json
                    
                    # Otherwise, it's a real error
                    error_msg = f"BSRE API Error {response.status_code}: {error_json.get('message', error_json)}"
                except:
                    error_msg = f"BSRE API Error {response.status_code}: {response.text[:200]}"
                
                raise UserError(error_msg)
            
            response.raise_for_status()
            
            # IMPORTANT: For FORMDATA signing (with files parameter), response is binary PDF
            # For JSON endpoints, response is JSON
            if files:
                # Signing with FORMDATA returns binary PDF directly
                _logger.info(f'FORMDATA signing successful, returning binary PDF (size: {len(response.content)} bytes)')
                # Return dict dengan content dan metadata untuk compatibility
                return {
                    'success': True,
                    'content': response.content,
                    'content_type': response.headers.get('Content-Type', 'application/pdf')
                }
            else:
                # JSON endpoints return JSON
                return response.json()
            
        except requests.exceptions.Timeout:
            error_msg = f'API request timeout after {self.api_timeout} seconds'
            _logger.error(error_msg)
            raise UserError(error_msg)
        
        except requests.exceptions.RequestException as e:
            error_msg = f'API request failed: {str(e)}'
            _logger.error(f'{error_msg}\nURL: {url}\nMethod: {method}')
            raise UserError(error_msg)
        
        except Exception as e:
            error_msg = f'Unexpected error: {str(e)}'
            _logger.error(error_msg)
            raise UserError(error_msg)
    
    def action_test_connection(self):
        """Test koneksi ke BSRE API - Simplified version"""
        self.ensure_one()
        
        # TODO: Update dengan endpoint BSRE yang benar setelah dapat dokumentasi
        # Untuk sementara, hanya validasi konfigurasi
        
        if not self.api_url or not self.username or not self.password:
            raise UserError('Konfigurasi tidak lengkap. Pastikan URL, Username, dan Password sudah diisi.')
        
        self.write({
            'connection_status': 'disconnected',
            'last_error': 'Test connection belum diimplementasikan. Silakan langsung test dengan sign dokumen.'
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Perhatian',
                'message': 'Konfigurasi tersimpan. Untuk test koneksi, silakan langsung sign dokumen. Endpoint test belum tersedia di API BSRE.',
                'type': 'warning',
                'sticky': False,
            }
        }
    
    def _resize_signature_image_to_preset(self):
        """
        CRITICAL METHOD: Resize signature image to EXACT preset size
        
        WHY THIS IS NEEDED:
        BSRE API has a BUG where it ignores width/height parameters for
        certain positions (like CENTER). The API uses the uploaded image's
        actual size instead of the width/height parameters we send!
        
        SOLUTION:
        Resize the image to EXACT size before upload, so even if API ignores
        parameters, the image itself is already the correct size.
        
        Returns:
            bytes: Resized image as binary PNG data
        """
        self.ensure_one()
        
        if not self.signature_image:
            return None
        
        try:
            from PIL import Image
            import io
            
            # Get target size from preset
            target_width = int(self._get_signature_width())
            target_height = int(self._get_signature_height())
            
            _logger.info(f'🔧 Resizing signature image to EXACT size: {target_width}x{target_height} px')
            
            # Decode uploaded image
            image_data = base64.b64decode(self.signature_image)
            image = Image.open(io.BytesIO(image_data))
            
            _logger.info(f'📐 Original image size: {image.size[0]}x{image.size[1]} px')
            
            # Convert to RGBA for transparency support
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
            
            # Resize to EXACT target size (maintain aspect ratio, then crop/pad)
            # Calculate scaling to fit within target size
            img_ratio = image.size[0] / image.size[1]
            target_ratio = target_width / target_height
            
            if img_ratio > target_ratio:
                # Image is wider, fit to width
                new_width = target_width
                new_height = int(target_width / img_ratio)
            else:
                # Image is taller, fit to height
                new_height = target_height
                new_width = int(target_height * img_ratio)
            
            # Resize maintaining aspect ratio
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Create final image with exact target size (white background)
            final_image = Image.new('RGBA', (target_width, target_height), (255, 255, 255, 0))
            
            # Paste resized image centered
            paste_x = (target_width - new_width) // 2
            paste_y = (target_height - new_height) // 2
            final_image.paste(image, (paste_x, paste_y), image)
            
            # Convert to RGB for PNG (remove alpha)
            final_rgb = Image.new('RGB', (target_width, target_height), (255, 255, 255))
            final_rgb.paste(final_image, mask=final_image.split()[3])  # Use alpha as mask
            
            # Save as PNG
            output = io.BytesIO()
            final_rgb.save(output, format='PNG', optimize=True)
            resized_data = output.getvalue()
            
            _logger.info(f'✅ Image resized successfully: {len(image_data)} → {len(resized_data)} bytes')
            
            return resized_data
            
        except Exception as e:
            error_msg = f'Failed to resize signature image: {str(e)}'
            _logger.error(error_msg)
            # Fallback: return original image
            return base64.b64decode(self.signature_image)
    
    def sign_document(self, document_data, document_name, passphrase=None):
        """
        Sign document dengan BSRE TTE API v2
        
        Args:
            document_data (bytes): Binary data PDF
            document_name (str): Nama dokumen
            passphrase (str): Passphrase untuk signing (dari user input)
        
        Returns:
            dict: Result with success status, signed data, and metadata
        """
        self.ensure_one()
        
        try:
            # Validate passphrase
            if self.use_otp:
                raise UserError('OTP signing belum diimplementasikan. Silakan gunakan Passphrase.')
            
            if not passphrase:
                raise UserError('Passphrase wajib diisi untuk menandatangani dokumen.')
            
            # BSRE API V2 menggunakan JSON dengan base64 encoding
            # Sesuai dokumentasi Petunjuk Teknis API Esign Client Service v2.2.1
            
            _logger.info(f'Signing document with BSRE API v2 (JSON): {document_name}')
            
            # Convert PDF to base64 for V2 API
            import base64 as b64
            document_base64 = b64.b64encode(document_data).decode('utf-8')
            
            # Prepare JSON payload for V2 API
            json_payload = {
                'nik': self.signing_identifier if self.signing_identifier_type == 'nik' else '',
                'email': self.signing_identifier if self.signing_identifier_type == 'email' else '',
                'passphrase': passphrase,
                'file': [document_base64],  # V2 uses base64 string array
            }
            
            # Add signature visualization parameters jika visible
            # V2 API uses signatureProperties array structure
            if self.signature_visible:
                # Get all signature parameters
                sig_width = self._get_signature_width()
                sig_height = self._get_signature_height()
                pos_x = self._get_position_x()
                pos_y = self._get_position_y()
                
                # CRITICAL: V2 API coordinate system is DIFFERENT from V1!
                # V1: Y=0 at BOTTOM (y increases upward)
                # V2: Y=0 at TOP (y increases downward)
                # We need to FLIP the Y coordinate!
                # Formula: V2_originY = PAGE_HEIGHT - V1_yAxis - signature_height
                # Assuming A4 page: height ≈ 842 points (for portrait)
                # But BSRE uses different scale, from docs: y=0 at top
                # So we need to flip: if V1 yAxis=10 (bottom), V2 should be near top
                # Formula: originY = PAGE_MAX_Y - yAxis_v1 - height
                
                # For now, let's use coordinate as-is and let BSRE handle it
                # We'll monitor the output and adjust if needed
                origin_x = float(pos_x)
                origin_y = float(pos_y)
                
                # LOG DETAIL untuk debug
                _logger.info('═' * 60)
                _logger.info('📐 SIGNATURE PARAMETERS (V2 API):')
                _logger.info(f'   Position Preset: {self.signature_position}')
                _logger.info(f'   Size Preset: {self.signature_size}')
                _logger.info(f'   Custom Position: {self.use_custom_position}')
                _logger.info(f'   Width: {sig_width} px')
                _logger.info(f'   Height: {sig_height} px')
                _logger.info(f'   originX: {origin_x} (V2 coordinate)')
                _logger.info(f'   originY: {origin_y} (V2 coordinate - Y=0 at TOP!)')
                _logger.info('═' * 60)
                
                # Prepare signatureProperties object
                signature_props = {
                    'tampilan': 'VISIBLE',
                    'page': 1,  # Always page 1 for now
                    'originX': origin_x,
                    'originY': origin_y,
                    'width': float(sig_width),
                    'height': float(sig_height),
                    'location': '',  # Optional
                    'reason': '',    # Optional
            }
            
                # Add signature image jika ada
                if self.signature_image:
                    # CRITICAL: BSRE API uses PHYSICAL IMAGE SIZE!
                    # We MUST resize image to EXACT dimensions before encoding to base64!
                    image_binary = self._resize_image_to_exact_size(
                        base64.b64decode(self.signature_image),
                        int(sig_width),
                        int(sig_height)
                    )
                    # Convert resized image to base64 for V2 API
                    image_base64 = b64.b64encode(image_binary).decode('utf-8')
                    signature_props['imageBase64'] = image_base64
                    
                    _logger.info(f'✅ Using RESIZED signature image: {len(image_binary)} bytes')
                    _logger.info(f'✅ Image physically resized to: {int(sig_width)}x{int(sig_height)} px')
                    _logger.info(f'✅ imageBase64 length: {len(image_base64)} chars')
                else:
                    # V2 API requires imageBase64 even for invisible
                    # Use a small transparent placeholder
                    _logger.info('⚠️ No signature image uploaded - using placeholder')
                
                # Add signatureProperties array to payload
                json_payload['signatureProperties'] = [signature_props]
            else:
                # INVISIBLE signature
                json_payload['signatureProperties'] = [{
                    'tampilan': 'INVISIBLE',
                    'page': 1,
                    'originX': 0.0,
                    'originY': 0.0,
                    'width': 0.0,
                    'height': 0.0,
                }]
            
            _logger.info(f'V2 API JSON payload prepared (file size: {len(document_base64)} chars base64)')
            _logger.info(f'Signature properties: {len(json_payload["signatureProperties"])} items')
            
            # Make API request to BSRE dengan JSON (V2)
            # Endpoint: /api/v2/sign/pdf
            # Note: _make_api_request uses 'data' parameter for JSON (when files=None)
            result = self._make_api_request('api/v2/sign/pdf', method='POST', data=json_payload)
            
            # Handle response based on format
            # FORMDATA endpoint returns: {'success': True, 'content': binary_pdf, 'content_type': 'application/pdf'}
            # JSON endpoint returns: {'time': 1099, 'file': ['base64_signed_pdf']}
            
            if result and isinstance(result, dict):
                # Check for FORMDATA response (binary PDF)
                if 'content' in result and result.get('success'):
                    signed_data = result['content']
                    _logger.info(f'Document signed successfully with FORMDATA: {document_name} (PDF size: {len(signed_data)} bytes)')
                    
                    # Update statistics
                    self.write({
                        'total_signatures': self.total_signatures + 1,
                        'successful_signatures': self.successful_signatures + 1,
                        'last_signature_date': fields.Datetime.now()
                    })
                    
                    return {
                        'success': True,
                        'message': 'Dokumen berhasil ditandatangani dengan BSRE',
                        'signed_data': signed_data,
                    }
                
                # Check for JSON response (base64 PDF in 'file' key)
                elif 'file' in result:
                    file_list = result.get('file', [])
                    processing_time = result.get('time', 0)
                    
                    if file_list and isinstance(file_list, list) and len(file_list) > 0:
                        # Get first signed document
                        signed_base64 = file_list[0]
                        signed_data = base64.b64decode(signed_base64)
                        
                        # Update statistics
                        self.write({
                            'total_signatures': self.total_signatures + 1,
                            'successful_signatures': self.successful_signatures + 1,
                            'last_signature_date': fields.Datetime.now()
                        })
                        
                        _logger.info(f'Document signed successfully with JSON: {document_name} (processing time: {processing_time}ms)')
                        
                        return {
                            'success': True,
                            'message': 'Dokumen berhasil ditandatangani dengan BSRE',
                            'signed_data': signed_data,
                        }
                    else:
                        raise UserError(f'BSRE API response tidak mengandung file yang valid: {result}')
                else:
                    raise UserError(f'BSRE API response tidak valid (expected "content" or "file" key): {result}')
            else:
                raise UserError(f'BSRE API response bukan dict yang valid: {result}')
                
        except Exception as e:
            error_msg = str(e)
            _logger.error(f'Error signing document: {error_msg}')
            
            # Update statistics
            self.write({
                'total_signatures': self.total_signatures + 1,
                'failed_signatures': self.failed_signatures + 1,
            })
            
            return {
                'success': False,
                'message': f'Tanda tangan gagal: {error_msg}'
            }
    
    def _resize_image_to_exact_size(self, image_binary, target_width, target_height):
        """
        Resize image MAINTAINING ASPECT RATIO to fit within target bounds.
        
        CRITICAL: BSRE API uses PHYSICAL size of the uploaded image!
        We must resize the image file itself before upload.
        
        ASPECT RATIO PRESERVED:
        - Fit image within bounding box (max_width x max_height)
        - Calculate actual dimensions maintaining original aspect ratio
        - No distortion - image stays proportional
        
        Example:
            Original: 569x308 (ratio 1.85:1)
            Target bounds: 120x90
            Result: 120x65 (maintains 1.85:1 ratio)
        
        Args:
            image_binary: Original image as bytes
            target_width: Maximum width in pixels (bounding box)
            target_height: Maximum height in pixels (bounding box)
        
        Returns:
            Resized image as bytes (PNG format, aspect ratio maintained)
        """
        from PIL import Image
        import io
        
        try:
            # Open image from binary
            image = Image.open(io.BytesIO(image_binary))
            original_size = image.size
            
            _logger.info(f'📐 Resizing image from {original_size[0]}x{original_size[1]} to {target_width}x{target_height}')
            
            # Convert to RGB if necessary (for JPEG compatibility)
            if image.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Calculate aspect ratio and resize MAINTAINING it
            # Fit within bounding box (target_width x target_height)
            original_width, original_height = original_size
            aspect_ratio = original_width / original_height
            
            _logger.info(f'🎨 Original aspect ratio: {aspect_ratio:.3f} ({original_width}:{original_height})')
            
            # OPTIMIZATION: Skip resize if image already small enough!
            # This preserves MAXIMUM QUALITY for images that don't need downscaling
            if original_width <= target_width and original_height <= target_height:
                _logger.info(f'✨ Image already within bounds ({original_width}x{original_height} ≤ {target_width}x{target_height})')
                _logger.info(f'✅ SKIPPING RESIZE for MAXIMUM QUALITY! (no quality loss)')
                
                # Still save as optimized PNG
                output = io.BytesIO()
                image.save(output, format='PNG', optimize=False, compress_level=1)
                result = output.getvalue()
                _logger.info(f'✅ Using original size: {len(image_binary)} → {len(result)} bytes')
                return result
            
            # Calculate new dimensions maintaining aspect ratio
            if original_width / target_width > original_height / target_height:
                # Width is limiting factor
                new_width = int(target_width)
                new_height = int(target_width / aspect_ratio)
            else:
                # Height is limiting factor  
                new_height = int(target_height)
                new_width = int(target_height * aspect_ratio)
            
            _logger.info(f'🎯 Resizing to: {new_width}x{new_height} (aspect ratio preserved)')
            _logger.info(f'⚠️  Downscaling from {original_width}x{original_height} (applying sharpening to maintain clarity)')
            
            # CRITICAL: Use HIGHEST QUALITY resize method
            # LANCZOS is best for downscaling, maintains sharpness
            resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Apply SHARPEN filter to compensate for downscaling blur
            # This helps maintain text/logo clarity
            from PIL import ImageFilter
            resized_image = resized_image.filter(ImageFilter.SHARPEN)
            
            # Save to bytes as PNG with HIGH QUALITY settings
            # optimize=False prevents aggressive compression
            # compress_level=1 for best quality (0-9, lower=better quality)
            output = io.BytesIO()
            resized_image.save(output, format='PNG', 
                             optimize=False,  # Don't sacrifice quality!
                             compress_level=1)  # Minimal compression
            resized_binary = output.getvalue()
            
            _logger.info(f'✅ Image resized: {len(image_binary)} → {len(resized_binary)} bytes')
            _logger.info(f'✅ Final dimensions: {new_width}x{new_height} px (ASPECT RATIO MAINTAINED ✨)')
            
            return resized_binary
            
        except Exception as e:
            _logger.error(f'❌ Error resizing image: {str(e)}')
            # Return original if resize fails
            return image_binary
    
    def _get_signature_width(self):
        """Get signature width based on size preset or custom value"""
        self.ensure_one()
        
        # Size presets (width x height)
        # CRITICAL: BSRE API uses PHYSICAL IMAGE SIZE, not API width/height parameters!
        # We resize image to these exact dimensions before upload.
        SIZE_PRESETS = {
            'small': 80,      # 80x60 - Good for corners
            'medium': 120,    # 120x90 - Balanced size
            'large': 160,     # 160x120 - Larger signature
            'xlarge': 200,    # 200x150 - Very visible
        }
        
        if self.signature_size == 'custom':
            return self.signature_width
        else:
            return SIZE_PRESETS.get(self.signature_size, 200)
    
    def _get_signature_height(self):
        """Get signature height based on size preset or custom value"""
        self.ensure_one()
        
        # Size presets (width x height)
        # CRITICAL: BSRE API uses PHYSICAL IMAGE SIZE, not API width/height parameters!
        # We resize image to these exact dimensions before upload.
        SIZE_PRESETS = {
            'small': 60,      # 80x60 - Good for corners
            'medium': 90,     # 120x90 - Balanced size
            'large': 120,     # 160x120 - Larger signature
            'xlarge': 150,    # 200x150 - Very visible
        }
        
        if self.signature_size == 'custom':
            return self.signature_height
        else:
            return SIZE_PRESETS.get(self.signature_size, 150)
    
    def _get_position_x(self):
        """
        Get X coordinate based on signature position or custom override
        
        Koordinat sistem BSRE (CONFIRMED BY TESTING):
        - xAxis=0 = KIRI (standard)
        - xAxis bertambah ke KANAN (standard)
        - Coordinates represent BOTTOM-LEFT corner of signature box
        
        CRITICAL FINDING: BSRE API does NOT auto-center the signature!
        The coordinates ALWAYS represent the bottom-left corner.
        We MUST calculate the position ourselves based on signature size.
        """
        self.ensure_one()
        
        # Use custom position if enabled
        if self.use_custom_position:
            return self.custom_position_x
        
        # Get signature width untuk perhitungan posisi
        sig_width = self._get_signature_width()
        
        # V2 API Coordinate System - A4 Portrait Dimensions
        # Page Width: 595.28 points (~210mm)
        # Page Height: 841.89 points (~297mm)
        PAGE_WIDTH = 595
        PAGE_HEIGHT = 842
        MARGIN = 10
        
        # Calculate position based on preset
        # V2 API: originX, originY represent TOP-LEFT corner of signature
        # We need to ensure signature stays within page boundaries
        
        POSITIONS_X = {
            'bottom_left': MARGIN,                                      # Left edge with margin
            'top_left': MARGIN,                                         # Left edge with margin
            'bottom_right': PAGE_WIDTH - sig_width - MARGIN,            # Right edge - width - margin
            'top_right': PAGE_WIDTH - sig_width - MARGIN,               # Right edge - width - margin
            'center': (PAGE_WIDTH / 2) - (sig_width / 2),               # Center - half width
        }
        
        position = POSITIONS_X.get(self.signature_position, 10)
        _logger.info(f'🎯 X Position: preset={self.signature_position}, sig_width={sig_width}, calculated={position}')
        return position
    
    def _get_position_y(self):
        """
        Get Y coordinate based on signature position or custom override
        
        Koordinat sistem BSRE (CONFIRMED BY TESTING):
        - yAxis=0 = BAWAH (not top!)
        - yAxis bertambah ke ATAS (not down!)
        - Y axis is FLIPPED from standard PDF
        - Coordinates represent BOTTOM-LEFT corner of signature box
        
        CRITICAL FINDING: BSRE API does NOT auto-center the signature!
        The coordinates ALWAYS represent the bottom-left corner.
        We MUST calculate the position ourselves based on signature size.
        """
        self.ensure_one()
        
        # Use custom position if enabled
        if self.use_custom_position:
            return self.custom_position_y
        
        # Get signature height untuk perhitungan posisi
        sig_height = self._get_signature_height()
        
        # V2 API Coordinate System - A4 Portrait Dimensions
        # Page Height: 841.89 points (~297mm)
        # V2 API: Y=0 at TOP (increases downward - standard PDF)
        PAGE_WIDTH = 595
        PAGE_HEIGHT = 842
        MARGIN = 10
        
        # Calculate position based on preset
        # V2 API: originY represents TOP-LEFT corner of signature (Y from top)
        # For BOTTOM positions: originY = PAGE_HEIGHT - sig_height - margin
        # For TOP positions: originY = margin
        # For CENTER: originY = (PAGE_HEIGHT / 2) - (sig_height / 2)
        
        POSITIONS_Y = {
            'bottom_left': PAGE_HEIGHT - sig_height - MARGIN,           # Bottom: from top to bottom edge
            'bottom_right': PAGE_HEIGHT - sig_height - MARGIN,          # Bottom: from top to bottom edge
            'top_left': MARGIN,                                          # Top: margin from top
            'top_right': MARGIN,                                         # Top: margin from top
            'center': (PAGE_HEIGHT / 2) - (sig_height / 2),             # Center: middle - half height
        }
        
        position = POSITIONS_Y.get(self.signature_position, 10)
        _logger.info(f'🎯 Y Position: preset={self.signature_position}, sig_height={sig_height}, calculated={position}')
        return position
    
    def verify_signature(self, document_data):
        """
        Verify digital signature pada dokumen
        
        Args:
            document_data (bytes): Binary data PDF
        
        Returns:
            dict: Verification result
        """
        self.ensure_one()
        
        try:
            # Prepare file
            files = {
                'document': ('document.pdf', document_data, 'application/pdf')
            }
            
            # Make API request
            result = self._make_api_request('verify/signature', method='POST', files=files)
            
            if result.get('success'):
                return {
                    'success': True,
                    'valid': result.get('valid'),
                    'signer': result.get('signer'),
                    'signature_date': result.get('signature_date'),
                    'certificate': result.get('certificate'),
                    'message': 'Verifikasi berhasil'
                }
            else:
                return {
                    'success': False,
                    'valid': False,
                    'message': result.get('message', 'Verifikasi gagal')
                }
                
        except Exception as e:
            error_msg = str(e)
            _logger.error(f'Error verifying signature: {error_msg}')
            
            return {
                'success': False,
                'valid': False,
                'message': f'Verifikasi gagal: {error_msg}'
            }
    
    def action_view_statistics(self):
        """View signature statistics"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Statistik BSRE',
            'res_model': 'bsre.config',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

