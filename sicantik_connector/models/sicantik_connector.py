# -*- coding: utf-8 -*-

import base64
import requests
import time
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class SicantikConnector(models.Model):
    """
    SICANTIK API Connector Service
    
    Handles all API communications with SICANTIK server including:
    - Data synchronization
    - Expiry date sync (workaround solution)
    - Error handling and retry logic
    - Rate limiting
    """
    _name = 'sicantik.connector'
    _description = 'SICANTIK API Connector Service'
    _rec_name = 'name'
    
    name = fields.Char(string='Connector Name', required=True, default='SICANTIK Connector')
    config_id = fields.Many2one('sicantik.config', string='Configuration', required=True)
    active = fields.Boolean(string='Active', default=True)
    
    # Statistics
    last_sync_date = fields.Datetime(string='Last Sync Date', readonly=True)
    last_expiry_sync_date = fields.Datetime(string='Last Expiry Sync Date', readonly=True)
    total_permits_synced = fields.Integer(string='Total Permits Synced', readonly=True)
    total_expiry_synced = fields.Integer(string='Total Expiry Synced', readonly=True)
    last_sync_duration = fields.Float(string='Last Sync Duration (seconds)', readonly=True)
    last_expiry_sync_duration = fields.Float(string='Last Expiry Sync Duration (seconds)', readonly=True)
    
    def _make_api_request(self, endpoint, params=None, method='GET', timeout=None):
        """
        Make API request to SICANTIK server
        
        Args:
            endpoint (str): API endpoint
            params (dict): Query parameters
            method (str): HTTP method
            timeout (int): Request timeout
        
        Returns:
            dict/list: API response data
        
        Raises:
            UserError: If request fails
        """
        self.ensure_one()
        
        if not timeout:
            timeout = self.config_id.api_timeout
        
        url = self.config_id.get_api_url(endpoint)
        
        try:
            _logger.info(f'API Request: {method} {url} params={params} timeout={timeout}s')
            
            if method == 'GET':
                response = requests.get(url, params=params, timeout=timeout)
            else:
                raise NotImplementedError(f'HTTP method {method} not implemented')
            
            _logger.info(f'Response status: {response.status_code}')
            response.raise_for_status()
            
            # Check if response is empty
            if not response.text or response.text.strip() == '':
                raise ValueError('API mengembalikan response kosong')
            
            # Check content type and parse accordingly
            content_type = response.headers.get('Content-Type', '')
            _logger.info(f'Content-Type: {content_type}')
            
            if 'xml' in content_type.lower() or response.text.strip().startswith('<?xml'):
                # Parse XML response
                _logger.info(f'Parsing XML response (length: {len(response.text)})')
                try:
                    root = ET.fromstring(response.text)
                    
                    # Check if it's a list of items (multiple records)
                    items = root.findall('.//item')
                    if items:
                        # Multiple items - convert to list of dicts
                        data = []
                        for item in items:
                            item_dict = {}
                            for child in item:
                                item_dict[child.tag] = child.text
                            data.append(item_dict)
                        _logger.info(f'XML parsed: {len(data)} items')
                    else:
                        # Single item - convert to dict
                        data = {}
                        for child in root.iter():
                            if child.text and child.text.strip():
                                data[child.tag] = child.text
                        _logger.info(f'XML parsed: single item with {len(data)} fields')
                    
                    return data
                    
                except ET.ParseError as xml_err:
                    _logger.error(f'XML parsing error: {xml_err}. Response: {response.text[:500]}')
                    raise ValueError(f'API tidak mengembalikan XML valid: {str(xml_err)}')
            else:
                # Try to parse JSON
                try:
                    data = response.json()
                    _logger.info(f'JSON parsed: {len(data) if isinstance(data, list) else "object"}')
                    return data
                except ValueError as json_err:
                    _logger.error(f'JSON parsing error. Response: {response.text[:500]}')
                    raise ValueError(f'API tidak mengembalikan JSON valid. Response: {response.text[:100]}')
        
        except requests.exceptions.Timeout:
            error_msg = f'API request timeout after {timeout} seconds'
            _logger.error(error_msg)
            raise UserError(error_msg)
        
        except requests.exceptions.RequestException as e:
            error_msg = f'API request failed: {str(e)}'
            _logger.error(error_msg)
            raise UserError(error_msg)
        
        except ValueError as e:
            error_msg = f'Invalid response: {str(e)}'
            _logger.error(error_msg)
            raise UserError(error_msg)
    
    def sync_permits(self, limit=None, offset=0, full_sync=False):
        """
        Sync permits from SICANTIK API
        
        Args:
            limit (int): Number of records to fetch per batch
            offset (int): Starting offset (only used if full_sync=False)
            full_sync (bool): If True, fetch ALL data with pagination loop
        
        Returns:
            dict: Sync statistics
        """
        self.ensure_one()
        start_time = time.time()
        
        if not limit:
            limit = self.config_id.sync_limit
        
        if full_sync:
            _logger.info('='*80)
            _logger.info(f'🔄 FULL SYNC: Starting (batch size: {limit})')
            _logger.info('='*80)
            
            # Full sync with pagination
            return self._sync_permits_full(limit)
        else:
            # Single batch sync (legacy behavior)
            _logger.info(f'Starting single batch sync: limit={limit}, offset={offset}')
            
            return self._sync_permits_single_batch(limit, offset)
    
    def _sync_permits_single_batch(self, limit, offset):
        """
        Sync permits - single batch mode
        
        Args:
            limit (int): Number of records to fetch
            offset (int): Starting offset
        
        Returns:
            dict: Sync statistics
        """
        start_time = time.time()
        
        try:
            # Fetch permits from API
            endpoint = f'listpermohonanterbit/limit/{limit}/offset/{offset}'
            data = self._make_api_request(endpoint)
            
            if not data:
                _logger.info('No permits to sync')
                return {'synced': 0, 'updated': 0, 'skipped': 0, 'failed': 0, 'duration': 0}
            
            synced = 0
            updated = 0
            skipped = 0
            failed = 0
            
            for permit_data in data:
                try:
                    result = self._process_permit_data(permit_data)
                    if result == 'synced':
                        synced += 1
                    elif result == 'updated':
                        updated += 1
                    elif result == 'skipped':
                        skipped += 1
                except Exception as e:
                    _logger.error(f'Error processing permit {permit_data.get("pendaftaran_id")}: {str(e)}')
                    failed += 1
            
            # Update statistics
            duration = time.time() - start_time
            self.write({
                'last_sync_date': fields.Datetime.now(),
                'total_permits_synced': self.total_permits_synced + synced,
                'last_sync_duration': duration
            })
            
            _logger.info('='*80)
            _logger.info(f'📊 Single batch sync completed:')
            _logger.info(f'  ✅ New:     {synced} records')
            _logger.info(f'  🔄 Updated: {updated} records')
            _logger.info(f'  ⏭️  Skipped: {skipped} records (invalid applicant names)')
            _logger.info(f'  ❌ Failed:  {failed} records')
            _logger.info(f'  ⏱️  Duration: {duration:.2f}s')
            _logger.info('='*80)
            
            return {
                'synced': synced,
                'updated': updated,
                'skipped': skipped,
                'failed': failed,
                'duration': duration
            }
        
        except Exception as e:
            _logger.error(f'Fatal error in permit sync: {str(e)}')
            raise UserError(f'Permit sync failed: {str(e)}')
    
    def _sync_permits_full(self, batch_size):
        """
        Sync ALL permits with pagination loop
        
        Args:
            batch_size (int): Number of records per API call
        
        Returns:
            dict: Sync statistics
        """
        start_time = time.time()
        
        try:
            total_synced = 0
            total_updated = 0
            total_skipped = 0
            total_failed = 0
            current_offset = 0
            batch_number = 1
            failed_batches = []  # Track failed batches for final report
            
            while True:
                batch_start = time.time()
                
                _logger.info(f'📦 Batch #{batch_number}: Fetching offset {current_offset}...')
                
                # Fetch batch from API with retry logic
                endpoint = f'listpermohonanterbit/limit/{batch_size}/offset/{current_offset}'
                data = None
                retry_count = 0
                max_retries = 3
                
                # Retry loop for failed API requests
                while retry_count < max_retries and data is None:
                    try:
                        data = self._make_api_request(endpoint)
                    except UserError as e:
                        retry_count += 1
                        if 'timeout' in str(e).lower():
                            if retry_count < max_retries:
                                _logger.warning(
                                    f'⚠️  Batch #{batch_number}: API timeout, retry {retry_count}/{max_retries} in 5s...'
                                )
                                time.sleep(5)  # Wait before retry
                            else:
                                _logger.error(
                                    f'❌ Batch #{batch_number}: Failed after {max_retries} retries (timeout). '
                                    f'Skipping offset {current_offset}.'
                                )
                                failed_batches.append({
                                    'batch': batch_number,
                                    'offset': current_offset,
                                    'reason': 'API timeout after retries'
                                })
                                # Skip this batch, continue to next
                                current_offset += batch_size
                                batch_number += 1
                                continue
                        else:
                            # Non-timeout error, re-raise
                            raise
                
                # Check if we got data
                if data is None or len(data) == 0:
                    _logger.info(f'✅ No more data at offset {current_offset}. Full sync complete!')
                    break
                
                records_in_batch = len(data)
                _logger.info(f'   Received {records_in_batch} records')
                
                # Process batch
                batch_synced = 0
                batch_updated = 0
                batch_skipped = 0
                batch_failed = 0
                
                for permit_data in data:
                    try:
                        result = self._process_permit_data(permit_data)
                        if result == 'synced':
                            batch_synced += 1
                        elif result == 'updated':
                            batch_updated += 1
                        elif result == 'skipped':
                            batch_skipped += 1
                    except Exception as e:
                        _logger.error(f'Error processing permit {permit_data.get("pendaftaran_id")}: {str(e)}')
                        batch_failed += 1
                
                # Update totals
                total_synced += batch_synced
                total_updated += batch_updated
                total_skipped += batch_skipped
                total_failed += batch_failed
                
                batch_duration = time.time() - batch_start
                _logger.info(
                    f'   ✅ New: {batch_synced} | 🔄 Updated: {batch_updated} | '
                    f'⏭️ Skipped: {batch_skipped} | ❌ Failed: {batch_failed} | '
                    f'⏱️ {batch_duration:.2f}s'
                )
                
                # CRITICAL: Commit per batch to prevent data loss on timeout
                self.env.cr.commit()
                _logger.debug(f'   💾 Batch #{batch_number} committed to database')
                
                # Move to next batch
                current_offset += batch_size
                batch_number += 1
                
                # Rate limiting
                if self.config_id.rate_limit_enabled:
                    delay = 1.0 / self.config_id.rate_limit_requests
                    _logger.debug(f'   Rate limiting: waiting {delay:.2f}s')
                    time.sleep(delay)
                
                # Safety break (max 100 batches = 30,000 records with default batch_size)
                if batch_number > 100:
                    _logger.warning('⚠️  Reached maximum batch limit (100). Stopping.')
                    break
            
            # Final statistics
            total_duration = time.time() - start_time
            total_processed = total_synced + total_updated + total_skipped + total_failed
            successful_batches = (batch_number - 1) - len(failed_batches)
            
            # Update connector statistics
            self.write({
                'last_sync_date': fields.Datetime.now(),
                'total_permits_synced': self.total_permits_synced + total_synced,
                'last_sync_duration': total_duration
            })
            
            # Final commit to ensure statistics are saved
            self.env.cr.commit()
            _logger.info('💾 Final statistics committed to database')
            
            _logger.info('='*80)
            _logger.info(f'🎉 FULL SYNC COMPLETED!')
            _logger.info(f'  📦 Total Batches:  {batch_number - 1} (✅ {successful_batches} success, ❌ {len(failed_batches)} failed)')
            _logger.info(f'  📊 Total Processed: {total_processed} records')
            _logger.info(f'  ✅ New:      {total_synced} records')
            _logger.info(f'  🔄 Updated:  {total_updated} records')
            _logger.info(f'  ⏭️  Skipped:  {total_skipped} records (invalid applicant names)')
            _logger.info(f'  ❌ Failed:   {total_failed} records')
            _logger.info(f'  ⏱️  Duration: {total_duration:.2f}s ({total_duration/60:.1f} minutes)')
            if total_processed > 0:
                _logger.info(f'  ⚡ Speed:    {total_processed/total_duration:.1f} records/second')
            
            # Log failed batches for manual review
            if failed_batches:
                _logger.warning('='*80)
                _logger.warning('⚠️  FAILED BATCHES (need manual review):')
                for fb in failed_batches:
                    _logger.warning(f'  • Batch #{fb["batch"]} (offset {fb["offset"]}): {fb["reason"]}')
                _logger.warning('='*80)
            else:
                _logger.info('='*80)
            
            return {
                'synced': total_synced,
                'updated': total_updated,
                'skipped': total_skipped,
                'failed': total_failed,
                'duration': total_duration,
                'batches': batch_number - 1,
                'successful_batches': successful_batches,
                'failed_batches': len(failed_batches),
                'failed_batch_details': failed_batches,
                'total_processed': total_processed
            }
        
        except Exception as e:
            _logger.error(f'Fatal error in full sync: {str(e)}')
            raise UserError(f'Full sync failed: {str(e)}')
    
    def _process_permit_data(self, data):
        """
        Process single permit data from API
        
        Args:
            data (dict): Permit data from API
        
        Returns:
            str: 'synced', 'updated', 'skipped', or 'failed'
        """
        registration_id = data.get('pendaftaran_id')
        if not registration_id:
            _logger.warning(f'Missing registration_id in data: {data}')
            return 'failed'
        
        # PHASE 1 FIX: Validate applicant name
        applicant_name = data.get('n_pemohon')
        if not applicant_name or str(applicant_name).strip() in ('', '0'):
            _logger.warning(
                f'⏭️  Skipping {registration_id}: '
                f'Invalid applicant name "{applicant_name}"'
            )
            return 'skipped'
        
        # Get permit type name
        permit_type_name = data.get('n_perizinan')
        if not permit_type_name:
            _logger.warning(f'Missing permit type for {registration_id}')
            return 'failed'
        
        # Find or create permit type
        permit_type = self.env['sicantik.permit.type'].search([
            ('name', '=', permit_type_name)
        ], limit=1)
        
        if not permit_type:
            _logger.info(f'Creating new permit type: {permit_type_name}')
            permit_type = self.env['sicantik.permit.type'].create({
                'name': permit_type_name,
                'last_sync_date': fields.Datetime.now()
            })
        
        # Prepare permit data
        permit_vals = {
            'registration_id': registration_id,
            'applicant_name': applicant_name,  # Already validated above
            'permit_type_name': permit_type_name,
            'permit_type_id': permit_type.id,
            'permit_number': data.get('no_surat'),
            'last_sync_date': fields.Datetime.now()
        }
        
        # Check if permit already exists
        existing_permit = self.env['sicantik.permit'].search([
            ('registration_id', '=', registration_id)
        ], limit=1)
        
        # Try to get applicant details and create/update partner
        # Only if permit doesn't have partner yet and permit_number is available
        # NOTE: This will call cekperizinan API which is slower, so we do it conditionally
        partner_id = None
        needs_partner = not existing_permit or not existing_permit.partner_id
        
        if needs_partner and applicant_name:
            # First, try to find existing partner by name (fast, no API call)
            existing_partner = self.env['res.partner'].search([
                ('name', 'ilike', applicant_name)
            ], limit=1)
            
            if existing_partner:
                partner_id = existing_partner.id
                _logger.debug(f'✅ Found existing partner: {existing_partner.name} (ID: {partner_id})')
            else:
                # If no existing partner, try to get detailed data from cekperizinan API
                # This is slower but gives us phone, address, etc.
                permit_number = data.get('no_surat')
                if permit_number:
                    try:
                        _logger.debug(f'🔍 Fetching detailed data for permit {permit_number}...')
                        detailed_data = self._get_permit_expiry_workaround(permit_number)
                        if detailed_data:
                            # Create or update partner from applicant data
                            partner = self._create_or_update_partner_from_applicant({
                                'n_pemohon': detailed_data.get('n_pemohon') or applicant_name,
                                'telp_pemohon': detailed_data.get('telp_pemohon', ''),
                                'a_pemohon': detailed_data.get('a_pemohon', ''),
                                'email_pemohon': detailed_data.get('email_pemohon', ''),
                            })
                            if partner:
                                partner_id = partner.id
                                # Safe access untuk mobile field
                                partner_model = self.env['res.partner']
                                if 'mobile' in partner_model._fields:
                                    mobile_display = getattr(partner, 'mobile', 'N/A')
                                elif 'phone' in partner_model._fields:
                                    mobile_display = getattr(partner, 'phone', 'N/A')
                                else:
                                    mobile_display = 'N/A'
                                _logger.info(f'✅ Created/updated partner: {partner.name} (ID: {partner_id}, Mobile: {mobile_display})')
                            # Also update expiry date if available
                            if detailed_data.get('d_berlaku_izin'):
                                permit_vals['expiry_date'] = detailed_data['d_berlaku_izin']
                                _logger.debug(f'📅 Updated expiry date: {permit_vals["expiry_date"]}')
                        else:
                            _logger.warning(f'⚠️ No detailed data returned from API for permit {permit_number}')
                    except Exception as e:
                        _logger.warning(f'⚠️ Error getting applicant details for {registration_id}: {str(e)}')
                        # Continue without partner - will be linked later via sync_partner_details_for_permits
                else:
                    _logger.debug(f'⚠️ No permit_number available for {registration_id}, skipping partner creation')
        
        # Link partner if found/created
        if partner_id:
            permit_vals['partner_id'] = partner_id
        
        if existing_permit:
            # Update existing permit
            existing_permit.write(permit_vals)
            _logger.debug(f'🔄 Updated existing permit: {registration_id}')
            return 'updated'
        else:
            # Create new permit
            permit_vals['status'] = 'active'
            self.env['sicantik.permit'].create(permit_vals)
            _logger.info(f'✅ Created new permit: {registration_id} - {applicant_name}')
            return 'synced'
    
    def sync_expiry_dates_workaround(self, max_permits=None):
        """
        WORKAROUND: Sync expiry dates using two-step API process
        
        This is a temporary solution until API is updated to include
        d_berlaku_izin in listpermohonanterbit response.
        
        Process:
        1. Get all permits without expiry date
        2. For each permit, call cekperizinan API
        3. Extract d_berlaku_izin and update permit
        
        Performance: ~0.15 seconds per permit
        
        Args:
            max_permits (int): Maximum permits to process (for testing)
        
        Returns:
            dict: Sync statistics
        """
        self.ensure_one()
        start_time = time.time()
        
        _logger.info('='*80)
        _logger.info('WORKAROUND: Starting expiry date sync')
        _logger.info('='*80)
        
        try:
            # Find permits without expiry date
            permits_to_sync = self.env['sicantik.permit'].search([
                ('expiry_date', '=', False),
                ('status', '=', 'active'),
                ('permit_number', '!=', False)
            ])
            
            if max_permits:
                permits_to_sync = permits_to_sync[:max_permits]
            
            total_permits = len(permits_to_sync)
            _logger.info(f'Found {total_permits} permits without expiry date')
            
            if total_permits == 0:
                _logger.info('No permits to sync')
                return {
                    'success': True,
                    'total': 0,
                    'synced': 0,
                    'failed': 0,
                    'duration': 0
                }
            
            synced_count = 0
            failed_count = 0
            
            for index, permit in enumerate(permits_to_sync, 1):
                try:
                    _logger.info(f'Processing {index}/{total_permits}: {permit.permit_number}')
                    
                    # Get expiry date from API
                    expiry_data = self._get_permit_expiry_workaround(permit.permit_number)
                    
                    if expiry_data and expiry_data.get('d_berlaku_izin'):
                        permit.write({
                            'expiry_date': expiry_data['d_berlaku_izin'],
                            'last_sync_date': fields.Datetime.now()
                        })
                        synced_count += 1
                        _logger.info(f'✅ Synced expiry: {expiry_data["d_berlaku_izin"]}')
                    else:
                        failed_count += 1
                        _logger.warning(f'⚠️ No expiry date found')
                    
                    # Rate limiting
                    if self.config_id.rate_limit_enabled:
                        time.sleep(1.0 / self.config_id.rate_limit_requests)
                    
                    # Progress update every 50 permits
                    if index % 50 == 0:
                        progress = (index / total_permits) * 100
                        elapsed = time.time() - start_time
                        estimated_total = (elapsed / index) * total_permits
                        remaining = estimated_total - elapsed
                        
                        _logger.info(f'Progress: {progress:.1f}% ({index}/{total_permits})')
                        _logger.info(f'Elapsed: {elapsed:.1f}s, Remaining: {remaining:.1f}s')
                
                except Exception as e:
                    failed_count += 1
                    _logger.error(f'❌ Error: {str(e)}')
                    continue
            
            # Update statistics
            duration = time.time() - start_time
            self.write({
                'last_expiry_sync_date': fields.Datetime.now(),
                'total_expiry_synced': self.total_expiry_synced + synced_count,
                'last_expiry_sync_duration': duration
            })
            
            _logger.info('='*80)
            _logger.info(f'WORKAROUND: Expiry sync completed')
            _logger.info(f'Total: {total_permits}, Synced: {synced_count}, Failed: {failed_count}')
            _logger.info(f'Duration: {duration:.2f} seconds')
            _logger.info('='*80)
            
            return {
                'success': True,
                'total': total_permits,
                'synced': synced_count,
                'failed': failed_count,
                'duration': duration
            }
        
        except Exception as e:
            _logger.error(f'Fatal error in expiry sync: {str(e)}')
            raise UserError(f'Expiry sync failed: {str(e)}')
    
    def _get_permit_expiry_workaround(self, permit_number):
        """
        WORKAROUND: Get expiry date for single permit
        
        Uses cekperizinan endpoint which requires base64 encoded permit number
        
        Args:
            permit_number (str): Permit number (no_surat)
        
        Returns:
            dict: Permit data including d_berlaku_izin, or None
        """
        try:
            # Encode permit number to base64
            no_izin_encoded = base64.b64encode(
                permit_number.encode('utf-8')
            ).decode('utf-8')
            
            # Call API
            data = self._make_api_request(
                'cekperizinan',
                params={'no_izin': no_izin_encoded},
                timeout=10
            )
            
            # Handle both single object and array response
            if isinstance(data, list) and len(data) > 0:
                return data[0]
            elif isinstance(data, dict):
                return data
            else:
                return None
        
        except Exception as e:
            _logger.warning(f'Error getting expiry for {permit_number}: {str(e)}')
            return None
    
    def _create_or_update_partner_from_applicant(self, applicant_data):
        """
        Create or update partner from applicant data
        
        Args:
            applicant_data (dict): Dictionary with keys:
                - n_pemohon (name)
                - telp_pemohon (phone)
                - a_pemohon (address)
                - email_pemohon (email, optional)
        
        Returns:
            res.partner: Partner record or None
        """
        applicant_name = applicant_data.get('n_pemohon', '').strip()
        if not applicant_name or applicant_name in ('', '0', '-', 'null'):
            _logger.warning(f'⚠️ Applicant name kosong atau invalid: {applicant_data.get("n_pemohon", "N/A")}')
            return None
        
        # Cari partner berdasarkan nama (case-insensitive)
        partner = self.env['res.partner'].search([
            ('name', 'ilike', applicant_name)
        ], limit=1)
        
        # Prepare partner data
        partner_vals = {
            'name': applicant_name,
        }
        
        # Update phone jika ada
        # Di Odoo 18.4, field 'phone' selalu tersedia di res.partner (contact)
        phone = applicant_data.get('telp_pemohon', '').strip()
        if phone and phone not in ('', '0', '-', 'null', 'None'):
            # Normalize phone number (remove spaces, dashes, etc)
            phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
            if phone.startswith('0'):
                # Convert 08xx to +628xx
                phone = '+62' + phone[1:]
            elif not phone.startswith('+'):
                phone = '+62' + phone
            
            # Di Odoo 18.4, field 'phone' selalu ada di res.partner
            # Gunakan phone sebagai primary field untuk nomor handphone
            partner_vals['phone'] = phone
            
            # Jika mobile juga tersedia, isi juga (untuk kompatibilitas)
            partner_model = self.env['res.partner']
            if 'mobile' in partner_model._fields:
                partner_vals['mobile'] = phone
        
        # Update address jika ada
        address = applicant_data.get('a_pemohon', '').strip()
        if address and address not in ('', '0', '-', 'null', 'None'):
            partner_vals['street'] = address
        
        # Update email jika ada
        email = applicant_data.get('email_pemohon', '').strip()
        if email and email not in ('', '0', '-', 'null', 'None'):
            partner_vals['email'] = email
        
        if partner:
            # Update existing partner (hanya update field yang kosong atau lebih lengkap)
            update_vals = {}
            
            # Di Odoo 18.4, field 'phone' selalu tersedia
            # Prioritas: update phone dulu (primary field untuk nomor handphone)
            if partner_vals.get('phone'):
                current_phone = getattr(partner, 'phone', False)
                
                # Cek apakah phone kosong atau None
                phone_is_empty = not current_phone or (isinstance(current_phone, str) and current_phone.strip() == '')
                
                if phone_is_empty:
                    # Phone kosong, update dengan nomor baru
                    update_vals['phone'] = partner_vals['phone']
                    _logger.debug(f'   Partner {partner.name} phone kosong, akan di-update dengan {partner_vals["phone"]}')
                elif partner_vals['phone'] != current_phone:
                    # Update jika nomor baru lebih lengkap (ada +62)
                    if partner_vals['phone'].startswith('+62') and (not current_phone or not current_phone.startswith('+62')):
                        update_vals['phone'] = partner_vals['phone']
                        _logger.debug(f'   Partner {partner.name} phone akan di-update dengan nomor yang lebih lengkap')
            
            # Jika mobile juga tersedia, update juga (untuk kompatibilitas)
            partner_model = self.env['res.partner']
            if 'mobile' in partner_model._fields and partner_vals.get('phone'):
                current_mobile = getattr(partner, 'mobile', False)
                
                if not current_mobile:
                    # Mobile kosong, update dengan nomor yang sama dengan phone
                    update_vals['mobile'] = partner_vals['phone']
                elif partner_vals['phone'].startswith('+62') and (not current_mobile or not current_mobile.startswith('+62')):
                    # Update jika nomor baru lebih lengkap
                    update_vals['mobile'] = partner_vals['phone']
            
            if not partner.street and partner_vals.get('street'):
                update_vals['street'] = partner_vals['street']
            if not partner.email and partner_vals.get('email'):
                update_vals['email'] = partner_vals['email']
            
            if update_vals:
                try:
                    partner.write(update_vals)
                    _logger.info(f'✅ Updated partner: {partner.name} with {list(update_vals.keys())}')
                except Exception as e:
                    _logger.error(f'❌ Error updating partner {partner.name}: {str(e)}', exc_info=True)
                    # Remove mobile dari update_vals jika error dan coba lagi tanpa mobile
                    if 'mobile' in update_vals:
                        update_vals_without_mobile = {k: v for k, v in update_vals.items() if k != 'mobile'}
                        if update_vals_without_mobile:
                            try:
                                partner.write(update_vals_without_mobile)
                                _logger.info(f'✅ Updated partner: {partner.name} with {list(update_vals_without_mobile.keys())} (mobile skipped)')
                            except Exception as e2:
                                _logger.error(f'❌ Error updating partner without mobile: {str(e2)}', exc_info=True)
        else:
            # Create new partner
            # Di Odoo 18.4, field 'phone' selalu tersedia
            # Pastikan phone diisi jika ada nomor dari API
            create_vals = partner_vals.copy()
            
            # Jika mobile juga tersedia, isi juga (untuk kompatibilitas)
            partner_model = self.env['res.partner']
            if 'mobile' in partner_model._fields and create_vals.get('phone'):
                # Copy phone ke mobile juga
                create_vals['mobile'] = create_vals['phone']
            
            try:
                partner = self.env['res.partner'].create(create_vals)
                phone_display = create_vals.get('phone', 'N/A')
                _logger.info(f'✅ Created new partner: {partner.name} (phone: {phone_display})')
            except Exception as e:
                _logger.error(f'❌ Error creating partner "{create_vals.get("name", "N/A")}": {str(e)}', exc_info=True)
                # Coba create tanpa mobile jika error (phone harus tetap ada)
                if 'mobile' in create_vals:
                    create_vals_without_mobile = {k: v for k, v in create_vals.items() if k != 'mobile'}
                    try:
                        partner = self.env['res.partner'].create(create_vals_without_mobile)
                        _logger.info(f'✅ Created new partner: {partner.name} (phone: {create_vals_without_mobile.get("phone", "N/A")}, mobile skipped)')
                    except Exception as e2:
                        _logger.error(f'❌ Error creating partner without mobile: {str(e2)}', exc_info=True)
                        return None
                else:
                    # Jika tidak ada mobile di create_vals, berarti error bukan karena mobile
                    _logger.error(f'❌ Cannot create partner, error: {str(e)}')
                    return None
        
        return partner
    
    def sync_partner_details_for_permits(self, max_permits=None):
        """
        Sync partner details (phone, address) untuk permit yang belum punya partner
        atau partner yang belum punya nomor telepon
        
        Process:
        1. Get permits without partner or partner without mobile
        2. For each permit, call cekperizinan API
        3. Create/update partner with full details
        4. Link partner to permit
        
        Args:
            max_permits (int): Maximum permits to process (for testing)
        
        Returns:
            dict: Sync statistics
        """
        self.ensure_one()
        start_time = time.time()
        
        _logger.info('='*80)
        _logger.info('🔄 Starting partner details sync for permits')
        _logger.info('='*80)
        
        try:
            # Find permits without partner or partner without phone
            # Note: Cannot use 'partner_id.phone' directly in domain, need to filter manually
            # Cari semua permit yang aktif dan punya permit_number
            all_permits = self.env['sicantik.permit'].search([
                ('permit_number', '!=', False),
                ('permit_number', '!=', ''),
                ('status', '=', 'active')
            ])
            
            _logger.info(f'Found {len(all_permits)} active permits with permit_number')
            
            # Filter permits that need partner sync
            # Di Odoo 18.4, field 'phone' selalu tersedia di res.partner
            permits_to_sync = self.env['sicantik.permit']
            permits_without_partner = 0
            permits_without_phone = 0
            
            for permit in all_permits:
                if not permit.partner_id:
                    # No partner - needs sync
                    permits_to_sync |= permit
                    permits_without_partner += 1
                elif permit.partner_id:
                    # Check if partner has phone field and if it's empty
                    # Di Odoo 18.4, phone selalu tersedia, jadi langsung cek
                    partner_phone = getattr(permit.partner_id, 'phone', False)
                    # Cek apakah phone kosong atau None
                    if not partner_phone or (isinstance(partner_phone, str) and partner_phone.strip() == ''):
                        # Has partner but no phone - needs sync
                        permits_to_sync |= permit
                        permits_without_phone += 1
            
            _logger.info(f'Permits breakdown: {permits_without_partner} without partner, {permits_without_phone} without phone')
            
            if max_permits:
                permits_to_sync = permits_to_sync[:max_permits]
            
            total_permits = len(permits_to_sync)
            _logger.info(f'Found {total_permits} permits to sync partner details')
            
            if total_permits == 0:
                _logger.info('No permits to sync')
                return {
                    'success': True,
                    'total': 0,
                    'synced': 0,
                    'failed': 0,
                    'duration': 0
                }
            
            synced_count = 0
            failed_count = 0
            
            # Log sample permits untuk debugging
            if total_permits > 0:
                sample_permits = permits_to_sync[:min(5, total_permits)]
                _logger.info(f'Sample permits to sync (first {len(sample_permits)}):')
                for sample in sample_permits:
                    partner_info = f'Partner: {sample.partner_id.name if sample.partner_id else "None"}'
                    phone_info = f'Phone: {getattr(sample.partner_id, "phone", "N/A") if sample.partner_id else "N/A"}'
                    _logger.info(f'  - {sample.registration_id}: {partner_info}, {phone_info}')
            
            _logger.info('='*80)
            _logger.info('Starting loop processing...')
            _logger.info('='*80)
            
            for index, permit in enumerate(permits_to_sync, 1):
                try:
                    _logger.info(f'[{index}/{total_permits}] Processing: {permit.registration_id} - {permit.applicant_name}')
                    
                    # Validasi: Pastikan permit_number ada
                    if not permit.permit_number or permit.permit_number.strip() == '':
                        failed_count += 1
                        _logger.warning(f'⚠️ Permit {permit.registration_id} tidak memiliki permit_number yang valid')
                        continue
                    
                    # Get detailed data from API
                    _logger.debug(f'   Calling API untuk permit_number: {permit.permit_number}')
                    detailed_data = self._get_permit_expiry_workaround(permit.permit_number)
                    
                    if detailed_data:
                        # Validasi: Pastikan ada nama pemohon
                        applicant_name = detailed_data.get('n_pemohon') or permit.applicant_name
                        if not applicant_name or applicant_name.strip() in ('', '0', '-', 'null'):
                            failed_count += 1
                            _logger.warning(f'⚠️ Permit {permit.registration_id} tidak memiliki nama pemohon yang valid')
                            continue
                        
                        # Create or update partner
                        try:
                            partner = self._create_or_update_partner_from_applicant({
                                'n_pemohon': applicant_name,
                                'telp_pemohon': detailed_data.get('telp_pemohon', ''),
                                'a_pemohon': detailed_data.get('a_pemohon', ''),
                                'email_pemohon': detailed_data.get('email_pemohon', ''),
                            })
                            
                            if partner:
                                # Link partner to permit
                                permit.write({'partner_id': partner.id})
                                
                                # Also update expiry date if available
                                if detailed_data.get('d_berlaku_izin') and not permit.expiry_date:
                                    permit.write({'expiry_date': detailed_data['d_berlaku_izin']})
                                
                                synced_count += 1
                                # Get phone number for display (phone selalu tersedia di Odoo 18.4)
                                phone_display = getattr(partner, 'phone', 'no phone')
                                _logger.info(f'✅ Synced partner: {partner.name} (phone: {phone_display})')
                            else:
                                failed_count += 1
                                _logger.warning(f'⚠️ Could not create/update partner untuk {permit.registration_id}')
                        except Exception as partner_error:
                            failed_count += 1
                            _logger.error(f'❌ Error creating/updating partner untuk {permit.registration_id}: {str(partner_error)}', exc_info=True)
                    else:
                        failed_count += 1
                        _logger.warning(f'⚠️ No detailed data from API untuk permit {permit.registration_id} (permit_number: {permit.permit_number})')
                    
                    # Log progress setiap 10 records (lebih sering untuk debugging)
                    if index % 10 == 0:
                        progress = (index / total_permits) * 100
                        elapsed = time.time() - start_time
                        estimated_total = (elapsed / index) * total_permits if index > 0 else 0
                        remaining = estimated_total - elapsed if estimated_total > elapsed else 0
                        
                        _logger.info(f'📊 Progress: {progress:.1f}% ({index}/{total_permits}) - Synced: {synced_count}, Failed: {failed_count}')
                        _logger.info(f'   Elapsed: {elapsed:.1f}s, Remaining: {remaining:.1f}s')
                    
                    # Rate limiting
                    if self.config_id.rate_limit_enabled:
                        time.sleep(1.0 / self.config_id.rate_limit_requests)
                
                except Exception as e:
                    failed_count += 1
                    _logger.error(f'❌ Error processing permit {permit.registration_id if permit else "Unknown"}: {str(e)}', exc_info=True)
                    continue
            
            # Log final status sebelum return
            _logger.info('='*80)
            _logger.info(f'Loop completed. Processed {total_permits} permits.')
            _logger.info(f'Final stats: Synced={synced_count}, Failed={failed_count}')
            _logger.info('='*80)
            
            duration = time.time() - start_time
            
            _logger.info('='*80)
            _logger.info(f'✅ Partner details sync completed')
            _logger.info(f'Total: {total_permits}, Synced: {synced_count}, Failed: {failed_count}')
            _logger.info(f'Duration: {duration:.2f} seconds')
            _logger.info('='*80)
            
            return {
                'success': True,
                'total': total_permits,
                'synced': synced_count,
                'failed': failed_count,
                'duration': duration
            }
        
        except Exception as e:
            _logger.error(f'Fatal error in partner details sync: {str(e)}')
            raise UserError(f'Partner details sync failed: {str(e)}')
    
    @api.model
    def cron_sync_expiry_dates(self):
        """
        Cron job to sync expiry dates
        Run daily at 02:00 AM
        """
        _logger.info('Starting scheduled expiry date sync...')
        
        connector = self.search([('active', '=', True)], limit=1)
        if not connector:
            _logger.error('No active connector found')
            return
        
        try:
            result = connector.sync_expiry_dates_workaround()
            
            if result['success']:
                _logger.info(f'Scheduled expiry sync completed: {result["synced"]} permits synced')
        
        except Exception as e:
            _logger.error(f'Scheduled expiry sync error: {str(e)}')
    
    def sync_permit_types(self):
        """
        Sync permit types from SICANTIK API
        
        Fetches all permit types from jenisperizinanlist endpoint
        and creates/updates permit type master data.
        
        Returns:
            dict: Sync statistics
        """
        self.ensure_one()
        start_time = time.time()
        
        _logger.info('Starting permit type sync...')
        
        try:
            # Fetch permit types from API
            data = self._make_api_request('jenisperizinanlist')
            
            if not data:
                _logger.info('No permit types to sync')
                return {'synced': 0, 'updated': 0, 'failed': 0}
            
            synced = 0
            updated = 0
            failed = 0
            
            for type_data in data:
                try:
                    type_name = type_data.get('jenis_perizinan')
                    if not type_name:
                        failed += 1
                        continue
                    
                    # Find existing permit type
                    permit_type = self.env['sicantik.permit.type'].search([
                        ('name', '=', type_name)
                    ], limit=1)
                    
                    type_vals = {
                        'name': type_name,
                        'code': type_data.get('id'),
                        'last_sync_date': fields.Datetime.now()
                    }
                    
                    if permit_type:
                        permit_type.write(type_vals)
                        updated += 1
                    else:
                        self.env['sicantik.permit.type'].create(type_vals)
                        synced += 1
                        
                except Exception as e:
                    _logger.error(f'Error processing permit type: {str(e)}')
                    failed += 1
            
            duration = time.time() - start_time
            _logger.info(f'Permit type sync completed in {duration:.2f}s: synced={synced}, updated={updated}, failed={failed}')
            
            return {
                'synced': synced,
                'updated': updated,
                'failed': failed,
                'duration': duration
            }
            
        except Exception as e:
            _logger.error(f'Fatal error in permit type sync: {str(e)}')
            raise UserError(f'Permit type sync failed: {str(e)}')
    
    def action_sync_permits(self):
        """Manual action to sync permits (single batch)"""
        self.ensure_one()
        
        result = self.sync_permits()  # full_sync=False by default
        
        # Build detailed message
        message_parts = []
        if result["synced"] > 0:
            message_parts.append(f'✅ Baru: {result["synced"]} records')
        if result["updated"] > 0:
            message_parts.append(f'🔄 Diperbarui: {result["updated"]} records')
        if result["skipped"] > 0:
            message_parts.append(f'⏭️ Dilewati: {result["skipped"]} records (nama pemohon tidak valid)')
        if result["failed"] > 0:
            message_parts.append(f'❌ Gagal: {result["failed"]} records')
        
        message = ' | '.join(message_parts) if message_parts else 'Tidak ada data untuk disinkronkan'
        
        # Determine notification type
        if result["synced"] > 0:
            notif_type = 'success'
        elif result["updated"] > 0:
            notif_type = 'info'
        else:
            notif_type = 'warning'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Sinkronisasi Selesai (Single Batch)',
                'message': message,
                'type': notif_type,
                'sticky': True,
            }
        }
    
    def action_full_sync_permits(self):
        """Manual action to full sync ALL permits with pagination"""
        self.ensure_one()
        
        result = self.sync_permits(full_sync=True)
        
        # Build comprehensive message for full sync
        message_parts = []
        if result.get("batches"):
            success_count = result.get("successful_batches", result["batches"])
            failed_count = result.get("failed_batches", 0)
            if failed_count > 0:
                message_parts.append(f'📦 {result["batches"]} batches (✅ {success_count} OK, ⚠️ {failed_count} timeout)')
            else:
                message_parts.append(f'📦 {result["batches"]} batches')
        
        if result.get("total_processed"):
            message_parts.append(f'📊 {result["total_processed"]} total processed')
        if result["synced"] > 0:
            message_parts.append(f'✅ Baru: {result["synced"]}')
        if result["updated"] > 0:
            message_parts.append(f'🔄 Updated: {result["updated"]}')
        if result["skipped"] > 0:
            message_parts.append(f'⏭️ Skipped: {result["skipped"]}')
        if result["failed"] > 0:
            message_parts.append(f'❌ Failed: {result["failed"]}')
        if result.get("duration"):
            minutes = result["duration"] / 60
            message_parts.append(f'⏱️ {minutes:.1f} menit')
        
        message = ' | '.join(message_parts) if message_parts else 'Tidak ada data untuk disinkronkan'
        
        # Determine notification type based on results
        failed_batch_count = result.get("failed_batches", 0)
        if failed_batch_count > 0:
            notif_type = 'warning'  # Has failures, show warning
        elif result.get("total_processed", 0) > 0:
            notif_type = 'success'  # All good
        else:
            notif_type = 'info'  # No data
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '🎉 Full Sync Selesai!' if failed_batch_count == 0 else '⚠️ Full Sync Selesai (dengan timeout)',
                'message': message,
                'type': notif_type,
                'sticky': True,
            }
        }
    
    def action_test_expiry_sync(self):
        """Manual action to test expiry sync"""
        self.ensure_one()
        
        result = self.sync_expiry_dates_workaround(max_permits=10)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Expiry Sync Test Completed',
                'message': f'Synced: {result["synced"]}, Failed: {result["failed"]}, Duration: {result["duration"]:.2f}s',
                'type': 'success' if result['synced'] > 0 else 'warning',
                'sticky': False,
            }
        }
    
    def action_sync_all_expiry(self):
        """Open wizard for full expiry sync"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sync All Expiry Dates',
            'res_model': 'sicantik.expiry.sync.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_connector_id': self.id}
        }
    
    def action_cleanup_invalid_permits(self):
        """
        Cleanup permits with invalid applicant names
        
        This removes existing permits that have invalid applicant names
        (e.g., '0', empty strings) that were imported before validation
        was implemented.
        
        NOTE: Skips permits that have related documents to avoid foreign key violations.
        """
        self.ensure_one()
        
        # Find permits with invalid applicant names
        invalid_permits = self.env['sicantik.permit'].search([
            ('applicant_name', 'in', ['0', '', False])
        ])
        
        total_invalid = len(invalid_permits)
        
        if total_invalid == 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Cleanup Selesai',
                    'message': 'Tidak ada records dengan nama pemohon tidak valid.',
                    'type': 'info',
                    'sticky': False,
                }
            }
        
        # Filter out permits that have documents (to avoid FK violation)
        permits_with_docs = []
        permits_to_delete = []
        
        for permit in invalid_permits:
            # Check if permit has documents
            has_documents = self.env['sicantik.document'].search_count([
                ('permit_id', '=', permit.id)
            ]) > 0
            
            if has_documents:
                permits_with_docs.append(permit)
            else:
                permits_to_delete.append(permit)
        
        deletable_count = len(permits_to_delete)
        protected_count = len(permits_with_docs)
        
        # Log details before deletion
        _logger.info('='*80)
        _logger.info(f'🧹 CLEANUP: Processing {total_invalid} permits with invalid applicant names')
        _logger.info(f'  • Deletable: {deletable_count} permits (no documents)')
        _logger.info(f'  • Protected: {protected_count} permits (have documents - will skip)')
        _logger.info('='*80)
        
        if deletable_count == 0:
            _logger.info('⚠️  No permits can be deleted (all have related documents)')
            _logger.info('='*80)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Cleanup Tidak Dapat Dilakukan',
                    'message': f'⚠️ Semua {total_invalid} records invalid masih memiliki dokumen terkait. Hapus dokumen terlebih dahulu atau biarkan records tetap ada.',
                    'type': 'warning',
                    'sticky': True,
                }
            }
        
        # Sample records for logging
        sample = permits_to_delete[:5]
        _logger.info('Sample records to delete:')
        for permit in sample:
            _logger.info(
                f'  Deleting: {permit.registration_id} | '
                f'Name: "{permit.applicant_name}" | '
                f'Type: {permit.permit_type_name}'
            )
        
        if deletable_count > 5:
            _logger.info(f'  ... and {deletable_count - 5} more records')
        
        if protected_count > 0:
            _logger.info('')
            _logger.info('Protected records (have documents):')
            sample_protected = permits_with_docs[:3]
            for permit in sample_protected:
                doc_count = self.env['sicantik.document'].search_count([
                    ('permit_id', '=', permit.id)
                ])
                _logger.info(
                    f'  Skipping: {permit.registration_id} | '
                    f'Name: "{permit.applicant_name}" | '
                    f'Documents: {doc_count}'
                )
            if protected_count > 3:
                _logger.info(f'  ... and {protected_count - 3} more protected records')
        
        # Delete only permits without documents
        permits_to_delete_recordset = self.env['sicantik.permit'].browse([p.id for p in permits_to_delete])
        permits_to_delete_recordset.unlink()
        
        _logger.info('')
        _logger.info(f'✅ Cleanup completed: {deletable_count} records deleted, {protected_count} skipped')
        _logger.info('='*80)
        
        # Build message
        if protected_count > 0:
            message = (
                f'✅ Berhasil menghapus {deletable_count} records | '
                f'⏭️ Dilewati: {protected_count} records (memiliki dokumen terkait)'
            )
        else:
            message = f'✅ Berhasil menghapus {deletable_count} records dengan nama pemohon tidak valid.'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Cleanup Selesai',
                'message': message,
                'type': 'success',
                'sticky': True,
            }
        }
    
    def action_analyze_database(self):
        """
        Analyze database untuk melihat kondisi data yang sudah diimport
        dan mencari informasi yang bisa digunakan untuk expiry date
        """
        self.ensure_one()
        
        _logger.info('='*80)
        _logger.info('🔍 DATABASE ANALYSIS: Starting...')
        _logger.info('='*80)
        
        # Query database langsung untuk analisis mendalam
        self.env.cr.execute("""
            SELECT 
                COUNT(*) as total_permits,
                COUNT(expiry_date) as has_expiry_date,
                COUNT(CASE WHEN expiry_date IS NULL THEN 1 END) as missing_expiry_date,
                COUNT(CASE WHEN expiry_date IS NOT NULL AND expiry_date < CURRENT_DATE THEN 1 END) as expired_count,
                COUNT(CASE WHEN expiry_date IS NOT NULL AND expiry_date >= CURRENT_DATE THEN 1 END) as active_expiry_count,
                COUNT(permit_number) as has_permit_number,
                COUNT(issue_date) as has_issue_date,
                COUNT(received_date) as has_received_date,
                COUNT(CASE WHEN days_until_expiry > 0 THEN 1 END) as positive_days,
                COUNT(CASE WHEN days_until_expiry < 0 THEN 1 END) as negative_days,
                COUNT(CASE WHEN days_until_expiry = 0 THEN 1 END) as zero_days
            FROM sicantik_permit
        """)
        
        stats = self.env.cr.dictfetchone()
        
        # Analisis per permit type
        self.env.cr.execute("""
            SELECT 
                permit_type_name,
                COUNT(*) as total,
                COUNT(expiry_date) as has_expiry,
                COUNT(CASE WHEN expiry_date IS NULL THEN 1 END) as missing_expiry,
                MIN(expiry_date) as earliest_expiry,
                MAX(expiry_date) as latest_expiry,
                AVG(days_until_expiry) as avg_days_until_expiry
            FROM sicantik_permit
            GROUP BY permit_type_name
            ORDER BY total DESC
            LIMIT 20
        """)
        
        permit_type_stats = self.env.cr.dictfetchall()
        
        # Analisis permit dengan days_until_expiry tapi tidak punya expiry_date
        self.env.cr.execute("""
            SELECT 
                id,
                registration_id,
                permit_number,
                permit_type_name,
                applicant_name,
                expiry_date,
                days_until_expiry,
                issue_date,
                received_date,
                create_date,
                last_sync_date
            FROM sicantik_permit
            WHERE expiry_date IS NULL 
              AND days_until_expiry != 0
            ORDER BY days_until_expiry DESC
            LIMIT 10
        """)
        
        anomaly_records = self.env.cr.dictfetchall()
        
        # Analisis permit dengan issue_date atau received_date
        self.env.cr.execute("""
            SELECT 
                COUNT(*) as total_with_dates,
                COUNT(issue_date) as has_issue_date,
                COUNT(received_date) as has_received_date,
                COUNT(CASE WHEN issue_date IS NOT NULL AND expiry_date IS NULL THEN 1 END) as has_issue_no_expiry,
                COUNT(CASE WHEN received_date IS NOT NULL AND expiry_date IS NULL THEN 1 END) as has_received_no_expiry,
                AVG(EXTRACT(EPOCH FROM (expiry_date - issue_date))/86400) as avg_days_issue_to_expiry,
                AVG(EXTRACT(EPOCH FROM (expiry_date - received_date))/86400) as avg_days_received_to_expiry
            FROM sicantik_permit
            WHERE expiry_date IS NOT NULL
        """)
        
        date_analysis = self.env.cr.dictfetchone()
        
        # Sample records untuk analisis detail
        self.env.cr.execute("""
            SELECT 
                id,
                registration_id,
                permit_number,
                permit_type_name,
                expiry_date,
                days_until_expiry,
                issue_date,
                received_date,
                create_date
            FROM sicantik_permit
            WHERE expiry_date IS NOT NULL
            ORDER BY expiry_date ASC
            LIMIT 5
        """)
        
        sample_with_expiry = self.env.cr.dictfetchall()
        
        self.env.cr.execute("""
            SELECT 
                id,
                registration_id,
                permit_number,
                permit_type_name,
                expiry_date,
                days_until_expiry,
                issue_date,
                received_date,
                create_date
            FROM sicantik_permit
            WHERE expiry_date IS NULL
            ORDER BY create_date DESC
            LIMIT 5
        """)
        
        sample_without_expiry = self.env.cr.dictfetchall()
        
        # Print comprehensive report
        _logger.info('')
        _logger.info('📊 OVERALL STATISTICS:')
        _logger.info(f'  Total Permits:           {stats["total_permits"]}')
        _logger.info(f'  Has Expiry Date:         {stats["has_expiry_date"]} ({stats["has_expiry_date"]*100/max(stats["total_permits"],1):.1f}%)')
        _logger.info(f'  Missing Expiry Date:     {stats["missing_expiry_date"]} ({stats["missing_expiry_date"]*100/max(stats["total_permits"],1):.1f}%)')
        _logger.info(f'  Already Expired:         {stats["expired_count"]}')
        _logger.info(f'  Active (not expired):    {stats["active_expiry_count"]}')
        _logger.info('')
        _logger.info('📋 FIELD AVAILABILITY:')
        _logger.info(f'  Has Permit Number:       {stats["has_permit_number"]} ({stats["has_permit_number"]*100/max(stats["total_permits"],1):.1f}%)')
        _logger.info(f'  Has Issue Date:          {stats["has_issue_date"]} ({stats["has_issue_date"]*100/max(stats["total_permits"],1):.1f}%)')
        _logger.info(f'  Has Received Date:      {stats["has_received_date"]} ({stats["has_received_date"]*100/max(stats["total_permits"],1):.1f}%)')
        _logger.info('')
        _logger.info('📅 DAYS UNTIL EXPIRY ANALYSIS:')
        _logger.info(f'  Positive (future):      {stats["positive_days"]}')
        _logger.info(f'  Negative (past):        {stats["negative_days"]}')
        _logger.info(f'  Zero:                   {stats["zero_days"]}')
        
        if date_analysis and date_analysis.get('total_with_dates', 0) > 0:
            _logger.info('')
            _logger.info('📈 DATE RELATIONSHIP ANALYSIS:')
            if date_analysis.get('avg_days_issue_to_expiry'):
                _logger.info(f'  Avg Days (Issue → Expiry): {date_analysis["avg_days_issue_to_expiry"]:.0f} days')
            if date_analysis.get('avg_days_received_to_expiry'):
                _logger.info(f'  Avg Days (Received → Expiry): {date_analysis["avg_days_received_to_expiry"]:.0f} days')
            _logger.info(f'  Has Issue Date (no expiry): {date_analysis.get("has_issue_no_expiry", 0)}')
            _logger.info(f'  Has Received Date (no expiry): {date_analysis.get("has_received_no_expiry", 0)}')
        
        if permit_type_stats:
            _logger.info('')
            _logger.info('🏷️  TOP 10 PERMIT TYPES:')
            for pt in permit_type_stats[:10]:
                expiry_pct = (pt['has_expiry'] * 100 / max(pt['total'], 1))
                _logger.info(f'  {pt["permit_type_name"]}:')
                _logger.info(f'    Total: {pt["total"]} | Has Expiry: {pt["has_expiry"]} ({expiry_pct:.1f}%) | Missing: {pt["missing_expiry"]}')
                if pt.get('earliest_expiry'):
                    _logger.info(f'    Expiry Range: {pt["earliest_expiry"]} to {pt["latest_expiry"]}')
                if pt.get('avg_days_until_expiry'):
                    _logger.info(f'    Avg Days Until Expiry: {pt["avg_days_until_expiry"]:.0f} days')
        
        if anomaly_records:
            _logger.info('')
            _logger.info('⚠️  ANOMALY DETECTED: Records with days_until_expiry but no expiry_date')
            _logger.info(f'  Found {len(anomaly_records)} records (showing first 10):')
            for rec in anomaly_records:
                _logger.info(f'    ID {rec["id"]}: {rec["registration_id"]} | Days: {rec["days_until_expiry"]} | Permit: {rec["permit_number"]}')
        
        if sample_with_expiry:
            _logger.info('')
            _logger.info('✅ SAMPLE RECORDS WITH EXPIRY DATE (earliest first):')
            for rec in sample_with_expiry:
                _logger.info(f'  {rec["registration_id"]}:')
                _logger.info(f'    Permit: {rec["permit_number"]} | Type: {rec["permit_type_name"]}')
                _logger.info(f'    Expiry: {rec["expiry_date"]} | Days: {rec["days_until_expiry"]}')
                if rec.get('issue_date'):
                    _logger.info(f'    Issue Date: {rec["issue_date"]}')
                if rec.get('received_date'):
                    _logger.info(f'    Received Date: {rec["received_date"]}')
        
        if sample_without_expiry:
            _logger.info('')
            _logger.info('❌ SAMPLE RECORDS WITHOUT EXPIRY DATE (newest first):')
            for rec in sample_without_expiry:
                _logger.info(f'  {rec["registration_id"]}:')
                _logger.info(f'    Permit: {rec["permit_number"]} | Type: {rec["permit_type_name"]}')
                _logger.info(f'    Days Until Expiry: {rec["days_until_expiry"]}')
                if rec.get('issue_date'):
                    _logger.info(f'    Issue Date: {rec["issue_date"]}')
                if rec.get('received_date'):
                    _logger.info(f'    Received Date: {rec["received_date"]}')
                _logger.info(f'    Created: {rec["create_date"]}')
        
        _logger.info('')
        _logger.info('='*80)
        _logger.info('✅ DATABASE ANALYSIS COMPLETED')
        _logger.info('='*80)
        
        # Build summary message
        summary_parts = []
        summary_parts.append(f'Total: {stats["total_permits"]} permits')
        summary_parts.append(f'✅ Expiry: {stats["has_expiry_date"]} ({stats["has_expiry_date"]*100/max(stats["total_permits"],1):.1f}%)')
        summary_parts.append(f'❌ Missing: {stats["missing_expiry_date"]} ({stats["missing_expiry_date"]*100/max(stats["total_permits"],1):.1f}%)')
        
        if date_analysis and date_analysis.get('avg_days_issue_to_expiry'):
            summary_parts.append(f'📅 Avg Issue→Expiry: {date_analysis["avg_days_issue_to_expiry"]:.0f} days')
        
        message = ' | '.join(summary_parts)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '📊 Database Analysis Results',
                'message': message,
                'type': 'info',
                'sticky': True,
            }
        }

