# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SicantikPermitInherit(models.Model):
    """
    Inherit sicantik.permit untuk improve display di wizard upload dokumen.
    Menampilkan info lengkap: Nama Pemohon | Jenis Izin | Nomor Izin
    """
    _inherit = 'sicantik.permit'
    
    # Display name yang lebih informatif untuk dropdown
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=False  # Tidak perlu store karena computed on-the-fly
    )
    
    @api.depends('applicant_name', 'permit_type_name', 'permit_number', 'registration_id')
    def _compute_display_name(self):
        """
        Compute display name dengan format informatif:
        [Reg ID] Nama Pemohon | Jenis Izin | No. Izin
        
        Contoh:
        [12345] PT ABC Indonesia | Izin Usaha Perdagangan | IUP/123/2025
        """
        for record in self:
            parts = []
            
            # Registration ID
            if record.registration_id:
                parts.append(f"[{record.registration_id}]")
            
            # Nama Pemohon
            if record.applicant_name:
                parts.append(record.applicant_name)
            else:
                parts.append("(Nama tidak tersedia)")
            
            # Jenis Izin
            if record.permit_type_name:
                parts.append(f"| {record.permit_type_name}")
            
            # Nomor Izin
            if record.permit_number:
                parts.append(f"| No. {record.permit_number}")
            else:
                parts.append("| (Belum ada nomor)")
            
            record.display_name = " ".join(parts)
    
    def name_get(self):
        """
        Override name_get untuk menampilkan display name yang informatif.
        Ini akan digunakan di semua Many2one dan dropdown.
        """
        result = []
        for record in self:
            # Build display name
            name_parts = []
            
            # Nama Pemohon (primary)
            if record.applicant_name:
                name_parts.append(record.applicant_name)
            else:
                name_parts.append(f"Reg {record.registration_id}")
            
            # Jenis Izin (secondary)
            if record.permit_type_name:
                name_parts.append(f"- {record.permit_type_name}")
            
            # Nomor Izin (tertiary)
            if record.permit_number:
                name_parts.append(f"({record.permit_number})")
            
            name = " ".join(name_parts)
            result.append((record.id, name))
        
        return result
    
    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, order=None):
        """
        Override name_search untuk search di multiple fields:
        - applicant_name (Nama Pemohon)
        - permit_type_name (Jenis Izin)
        - permit_number (Nomor Izin)
        - registration_id (ID Pendaftaran)
        
        Ini membuat search di dropdown lebih powerful!
        
        CRITICAL: Method ini harus return list of IDs, bukan recordset!
        """
        import logging
        _logger = logging.getLogger(__name__)
        
        if args is None:
            args = []
        
        _logger.info(f'🔍 _name_search called with name="{name}", operator={operator}, limit={limit}')
        _logger.info(f'🔍 Initial args: {args}')
        
        # Domain untuk search di multiple fields
        if name:
            # Build domain dengan OR logic untuk search di multiple fields
            search_domain = [
                '|', '|', '|',
                ('applicant_name', operator, name),
                ('permit_type_name', operator, name),
                ('permit_number', operator, name),
                ('registration_id', operator, name),
            ]
            
            # Combine dengan args existing menggunakan AND logic
            if args:
                # If args exist, we need to AND them with our search domain
                # Format: [search_domain] + args
                domain = search_domain + args
            else:
                domain = search_domain
        else:
            # No search term, just use original args
            domain = args if args else []
        
        _logger.info(f'🔍 Final domain: {domain}')
        
        # CRITICAL: Use self.search() instead of self._search() 
        # to get recordset, then extract IDs
        # This ensures proper access rights and filters are applied
        permits = self.search(domain, limit=limit, order=order)
        
        _logger.info(f'🔍 Found {len(permits)} permits')
        if permits:
            _logger.info(f'🔍 Sample results: {permits[:3].mapped("applicant_name")}')
        
        # Return list of IDs (not recordset!)
        # Odoo's name_search expects: list of IDs or list of (id, name) tuples
        # We return IDs and let name_get() handle the display
        return permits.ids

