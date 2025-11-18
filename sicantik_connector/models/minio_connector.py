# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MinioConnector(models.Model):
    """
    Model untuk konfigurasi dan koneksi ke MinIO Object Storage
    """
    _name = 'minio.connector'
    _description = 'MinIO Storage Connector'
    _rec_name = 'name'
    
    name = fields.Char(
        string='Nama Konfigurasi',
        required=True,
        default='MinIO Storage'
    )
    endpoint = fields.Char(
        string='MinIO Endpoint',
        required=True,
        default='minio_storage:9000',
        help='MinIO server endpoint (e.g., localhost:9000 atau minio_storage:9000 untuk Docker)'
    )
    access_key = fields.Char(
        string='Access Key',
        required=True,
        help='MinIO Access Key ID'
    )
    secret_key = fields.Char(
        string='Secret Key',
        required=True,
        help='MinIO Secret Access Key'
    )
    secure = fields.Boolean(
        string='Use HTTPS',
        default=False,
        help='Use secure (HTTPS) connection'
    )
    region = fields.Char(
        string='Region',
        default='us-east-1',
        help='MinIO region (default: us-east-1)'
    )
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    # Connection Status
    connection_status = fields.Selection([
        ('disconnected', 'Disconnected'),
        ('connected', 'Connected'),
        ('error', 'Error'),
    ], string='Status Koneksi', default='disconnected', readonly=True)
    
    last_connection_test = fields.Datetime(
        string='Last Connection Test',
        readonly=True
    )
    last_error = fields.Text(
        string='Last Error',
        readonly=True
    )
    
    # Statistics
    total_uploads = fields.Integer(
        string='Total Uploads',
        default=0,
        readonly=True
    )
    total_downloads = fields.Integer(
        string='Total Downloads',
        default=0,
        readonly=True
    )
    
    def _get_minio_client(self):
        """
        Get MinIO client instance
        
        Returns:
            Minio: MinIO client object
        """
        self.ensure_one()
        
        try:
            from minio import Minio
            import socket
            
            # Use endpoint exactly as stored - don't modify unless necessary
            endpoint = self.endpoint.strip()
            secure = self.secure
            
            # Only remove protocol if present (MinIO library doesn't need it)
            if endpoint.startswith('http://'):
                endpoint = endpoint[7:]
                secure = False
            elif endpoint.startswith('https://'):
                endpoint = endpoint[8:]
                secure = True
            
            # Remove any path after host:port (keep only host:port)
            if '/' in endpoint:
                endpoint = endpoint.split('/')[0]
            
            # Remove trailing slash
            endpoint = endpoint.rstrip('/')
            
            # WORKAROUND: MinIO Python library 7.2.18 uses virtual-host style 
            # when endpoint contains underscore (e.g., minio_storage:9000)
            # This causes "invalid hostname" error. Solution: resolve to IP address
            if ':' in endpoint:
                host, port = endpoint.rsplit(':', 1)
                # If hostname contains underscore, resolve to IP to force path-style
                if '_' in host:
                    try:
                        _logger.info(f'Resolving hostname {host} to IP address (workaround for underscore issue)')
                        ip_address = socket.gethostbyname(host)
                        endpoint = f'{ip_address}:{port}'
                        _logger.info(f'Using IP address: {endpoint}')
                    except socket.gaierror:
                        _logger.warning(f'Could not resolve {host} to IP, using original endpoint')
                        # Keep original endpoint if resolution fails
            
            _logger.info(f'Creating MinIO client: endpoint={endpoint}, secure={secure}, region=None')
            
            # Create client WITHOUT region parameter
            # This forces MinIO to use path-style access instead of virtual-host style
            # Path-style: http://endpoint/bucket/object
            # Virtual-host: http://bucket.endpoint/object (causes invalid hostname error)
            client = Minio(
                endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=secure
                # Explicitly NOT setting region to force path-style access
            )
            
            return client
            
        except ImportError:
            raise UserError('Library MinIO tidak terinstall. Install dengan: pip install minio')
        except Exception as e:
            _logger.error(f'Error creating MinIO client: {str(e)}')
            _logger.error(f'Endpoint used: {self.endpoint}, Secure: {self.secure}')
            raise UserError(f'Error membuat MinIO client: {str(e)}')
    
    def action_test_connection(self):
        """Test connection to MinIO server"""
        self.ensure_one()
        
        try:
            _logger.info(f'Testing MinIO connection: endpoint={self.endpoint}, secure={self.secure}')
            
            client = self._get_minio_client()
            
            # Try to list buckets to test connection
            # This is the operation that fails with "invalid hostname" if virtual-host style is used
            _logger.info('Attempting to list buckets...')
            buckets = list(client.list_buckets())
            _logger.info(f'Successfully listed {len(buckets)} buckets')
            
            self.write({
                'connection_status': 'connected',
                'last_connection_test': fields.Datetime.now(),
                'last_error': False,
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Koneksi Berhasil',
                    'message': f'Terhubung ke MinIO. Ditemukan {len(buckets)} bucket(s).',
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            error_msg = str(e)
            _logger.error(f'MinIO connection test failed: {error_msg}')
            _logger.error(f'Endpoint: {self.endpoint}, Secure: {self.secure}')
            import traceback
            _logger.error(traceback.format_exc())
            
            self.write({
                'connection_status': 'error',
                'last_connection_test': fields.Datetime.now(),
                'last_error': error_msg,
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Koneksi Gagal',
                    'message': f'Gagal terhubung ke MinIO: {error_msg}',
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    def ensure_bucket_exists(self, bucket_name):
        """
        Ensure bucket exists, create if not
        
        Args:
            bucket_name (str): Name of the bucket
            
        Returns:
            bool: True if successful
        
        Raises:
            UserError: If bucket creation fails
        """
        self.ensure_one()
        
        if not bucket_name:
            raise UserError('Nama bucket tidak boleh kosong')
        
        try:
            _logger.info(f'Checking bucket existence: {bucket_name}')
            _logger.info(f'MinIO config: endpoint={self.endpoint}, secure={self.secure}')
            
            client = self._get_minio_client()
            
            # Check if bucket exists
            bucket_exists = client.bucket_exists(bucket_name)
            _logger.info(f'Bucket {bucket_name} exists: {bucket_exists}')
            
            if not bucket_exists:
                # Create bucket without region to avoid hostname issues
                _logger.info(f'Creating bucket: {bucket_name}')
                client.make_bucket(bucket_name)
                _logger.info(f'Bucket {bucket_name} created successfully')
            else:
                _logger.info(f'Bucket {bucket_name} already exists')
            
            return True
            
        except Exception as e:
            error_msg = str(e)
            _logger.error(f'Error ensuring bucket exists: {error_msg}')
            _logger.error(f'Endpoint: {self.endpoint}, Secure: {self.secure}')
            _logger.error(f'Bucket name: {bucket_name}')
            import traceback
            _logger.error(traceback.format_exc())
            raise UserError(f'Gagal membuat atau memastikan bucket "{bucket_name}" ada: {error_msg}')
    
    def upload_file(self, bucket_name, object_name, file_data, content_type='application/pdf'):
        """
        Upload file to MinIO
        
        Args:
            bucket_name (str): Name of the bucket
            object_name (str): Name of the object (path in bucket)
            file_data (bytes): File data to upload
            content_type (str): MIME type of the file
            
        Returns:
            dict: Result with success status and message
        """
        self.ensure_one()
        
        try:
            from io import BytesIO
            
            # Ensure bucket exists
            self.ensure_bucket_exists(bucket_name)
            
            # Get client
            client = self._get_minio_client()
            
            # Upload file
            file_stream = BytesIO(file_data)
            file_size = len(file_data)
            
            result = client.put_object(
                bucket_name=bucket_name,
                object_name=object_name,
                data=file_stream,
                length=file_size,
                content_type=content_type
            )
            
            # Update statistics
            self.write({'total_uploads': self.total_uploads + 1})
            
            _logger.info(f'File uploaded successfully: {bucket_name}/{object_name}')
            
            return {
                'success': True,
                'message': 'File berhasil diupload ke MinIO',
                'etag': result.etag,
                'bucket': bucket_name,
                'object_name': object_name,
            }
            
        except Exception as e:
            error_msg = str(e)
            _logger.error(f'Error uploading file to MinIO: {error_msg}')
            return {
                'success': False,
                'message': f'Error upload: {error_msg}'
            }
    
    def download_file(self, bucket_name, object_name):
        """
        Download file from MinIO
        
        Args:
            bucket_name (str): Name of the bucket
            object_name (str): Name of the object (path in bucket)
            
        Returns:
            dict: Result with success status and file data
        """
        self.ensure_one()
        
        try:
            # Get client
            client = self._get_minio_client()
            
            # Download file
            response = client.get_object(bucket_name, object_name)
            file_data = response.read()
            response.close()
            response.release_conn()
            
            # Update statistics
            self.write({'total_downloads': self.total_downloads + 1})
            
            _logger.info(f'File downloaded successfully: {bucket_name}/{object_name}')
            
            return {
                'success': True,
                'message': 'File berhasil didownload dari MinIO',
                'data': file_data,
                'bucket': bucket_name,
                'object_name': object_name,
            }
            
        except Exception as e:
            error_msg = str(e)
            _logger.error(f'Error downloading file from MinIO: {error_msg}')
            return {
                'success': False,
                'message': f'Error download: {error_msg}'
            }
    
    def delete_file(self, bucket_name, object_name):
        """
        Delete file from MinIO
        
        Args:
            bucket_name (str): Name of the bucket
            object_name (str): Name of the object (path in bucket)
            
        Returns:
            dict: Result with success status and message
        """
        self.ensure_one()
        
        try:
            # Get client
            client = self._get_minio_client()
            
            # Delete file
            client.remove_object(bucket_name, object_name)
            
            _logger.info(f'File deleted successfully: {bucket_name}/{object_name}')
            
            return {
                'success': True,
                'message': 'File berhasil dihapus dari MinIO',
                'bucket': bucket_name,
                'object_name': object_name,
            }
            
        except Exception as e:
            error_msg = str(e)
            _logger.error(f'Error deleting file from MinIO: {error_msg}')
            return {
                'success': False,
                'message': f'Error delete: {error_msg}'
            }
    
    def get_file_url(self, bucket_name, object_name, expires=3600):
        """
        Get presigned URL for file download
        
        Args:
            bucket_name (str): Name of the bucket
            object_name (str): Name of the object (path in bucket)
            expires (int): URL expiry time in seconds (default: 1 hour)
            
        Returns:
            str: Presigned URL
        """
        self.ensure_one()
        
        try:
            from datetime import timedelta
            
            # Get client
            client = self._get_minio_client()
            
            # Generate presigned URL
            url = client.presigned_get_object(
                bucket_name=bucket_name,
                object_name=object_name,
                expires=timedelta(seconds=expires)
            )
            
            return url
            
        except Exception as e:
            error_msg = str(e)
            _logger.error(f'Error generating presigned URL: {error_msg}')
            raise UserError(f'Error generate URL: {error_msg}')

