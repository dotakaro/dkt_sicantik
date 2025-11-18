-- Script untuk menghapus template WhatsApp SICANTIK yang sudah ada
-- Jalankan script ini di database Odoo sebelum upgrade modul jika ada error

-- Hapus variabel template yang sudah ada
DELETE FROM whatsapp_template_variable 
WHERE wa_template_id IN (
    SELECT id FROM whatsapp_template 
    WHERE template_name IN (
        'izin_selesai_diproses',
        'dokumen_baru_untuk_tandatangan',
        'dokumen_perlu_approval',
        'update_status_perizinan',
        'reminder_dokumen_pending',
        'peringatan_masa_berlaku_izin',
        'perpanjangan_izin_disetujui'
    )
);

-- Hapus template yang sudah ada
DELETE FROM whatsapp_template 
WHERE template_name IN (
    'izin_selesai_diproses',
    'dokumen_baru_untuk_tandatangan',
    'dokumen_perlu_approval',
    'update_status_perizinan',
    'reminder_dokumen_pending',
    'peringatan_masa_berlaku_izin',
    'perpanjangan_izin_disetujui'
);

