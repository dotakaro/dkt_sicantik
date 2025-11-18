# -*- coding: utf-8 -*-

def pre_init_hook(cr):
    """
    Hook yang dijalankan sebelum install/upgrade modul
    Menghapus template WhatsApp SICANTIK yang sudah ada untuk menghindari konflik
    """
    import logging
    _logger = logging.getLogger(__name__)
    
    _logger.info('='*80)
    _logger.info('🧹 PRE-INIT HOOK: Menghapus template WhatsApp SICANTIK yang sudah ada')
    _logger.info('='*80)
    
    template_names = [
        'izin_selesai_diproses',
        'dokumen_baru_untuk_tandatangan',
        'dokumen_perlu_approval',
        'update_status_perizinan',
        'reminder_dokumen_pending',
        'peringatan_masa_berlaku_izin',
        'perpanjangan_izin_disetujui'
    ]
    
    # Cek apakah tabel whatsapp_template ada
    cr.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'whatsapp_template'
        );
    """)
    
    table_exists = cr.fetchone()[0]
    
    if not table_exists:
        _logger.info('✅ Tabel whatsapp_template belum ada, tidak perlu cleanup')
        return
    
    try:
        # Hapus variabel template terlebih dahulu
        cr.execute("""
            DELETE FROM whatsapp_template_variable 
            WHERE wa_template_id IN (
                SELECT id FROM whatsapp_template 
                WHERE template_name IN %s
            );
        """, (tuple(template_names),))
        
        deleted_vars = cr.rowcount
        _logger.info(f'  Menghapus {deleted_vars} variabel template')
        
        # Hapus template
        cr.execute("""
            DELETE FROM whatsapp_template 
            WHERE template_name IN %s;
        """, (tuple(template_names),))
        
        deleted_templates = cr.rowcount
        _logger.info(f'✅ Berhasil menghapus {deleted_templates} template')
        
        # Commit perubahan
        cr.commit()
        
    except Exception as e:
        _logger.warning(f'⚠️  Error saat cleanup template: {str(e)}')
        cr.rollback()
    
    _logger.info('='*80)

