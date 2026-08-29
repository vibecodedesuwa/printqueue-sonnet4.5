/**
 * PrintQ Manager — Multi-lingual (English / Thai) Translation Module
 */

const translations = {
    en: {
        // General & Brand
        brand_name: "PrintQ",
        brand_tagline: "Enterprise Print Queue & Management System",
        dashboard: "Dashboard",
        upload_print: "Upload & Print",
        a4_editor: "A4 Quick Editor",
        qr_mobile_print: "QR Mobile Print",
        admin_panel: "Admin Panel",
        kiosk_mode: "Kiosk Mode",
        api_docs: "API Docs",
        logout: "Log Out",
        welcome: "Welcome",
        status: "Status",
        online: "Online",
        offline: "Offline",

        // Landing & Auth
        landing_title: "Smart Enterprise Print Management",
        landing_subtitle: "Unified Print Queue for Windows, Mac, Linux, iOS, iPadOS & Android with Authentik SSO & Active Directory",
        login_with_echostory: "Login with EchoStory",
        login_with_ad: "Login with Active Directory",
        ad_username: "AD Username",
        ad_password: "Password",
        login_btn: "Log In",
        ad_auth_title: "Active Directory Login",
        sso_auth_title: "Authentik SSO Login",
        quick_start_desc: "Scan QR code to upload from smartphone or login to manage print jobs.",

        // Dashboard & Jobs
        my_print_jobs: "My Print Jobs",
        unclaimed_jobs: "Unclaimed Jobs Pool",
        no_jobs_found: "No active print jobs found.",
        no_unclaimed_jobs: "No unclaimed jobs in queue.",
        job_id: "Job ID",
        filename: "Filename",
        submitted_by: "Submitted By",
        pages: "Pages",
        size: "Size",
        submitted_at: "Time",
        actions: "Actions",
        release_print: "Print & Release",
        cancel: "Cancel",
        claim_job: "Claim Job",
        claim_desc: "Jobs submitted via AirPrint / Mopria or generic devices can be claimed here.",
        printer_status_title: "Printer Status",
        printer_ready: "Printer Ready & Accepting Jobs",
        printer_offline: "Printer Offline or Stopped",
        printer_busy: "Printing in progress",

        // Upload & Print
        upload_title: "Upload & Print Document",
        upload_subtitle: "Supports PDF, PNG, JPG, JPEG, WEBP, DOCX, DOC, TXT",
        drag_drop_text: "Drag & drop files here, or click to browse",
        copies: "Number of Copies",
        color_mode: "Color Mode",
        color_full: "Color",
        color_bw: "Black & White (Grayscale)",
        duplex_mode: "Print Mode",
        duplex_single: "Single-Sided",
        duplex_two: "Two-Sided (Duplex)",
        page_range: "Page Range (Optional)",
        page_range_help: "e.g. 1-5, 8, 11-13",
        submit_print_job: "Submit Print Job",

        // A4 Quick Editor
        editor_title: "Lightweight A4 Editor",
        editor_subtitle: "Create, format, paste images, and print A4 documents directly",
        office_editor: "Collabora Office Editor",
        office_editor_desc: "Use the complete Writer interface with reliable Thai text shaping and automatic saving.",
        new_document: "New document",
        open_document: "Open ODT/DOCX",
        document_title: "Document title",
        size_normal: "Normal",
        size_medium: "Medium",
        size_large: "Large",
        size_heading: "Heading",
        size_title: "Title",
        editor_default_heading: "Quick Document",
        editor_default_body: "Start typing your document text here...",
        editor_heading_placeholder: "Enter Document Heading...",
        editor_body_placeholder: "Type your text content here...",
        editor_font_size: "Font Size",
        editor_align_left: "Left",
        editor_align_center: "Center",
        editor_align_right: "Right",
        editor_bold: "Bold",
        editor_italic: "Italic",
        editor_insert_image: "Insert Image",
        editor_clear: "Clear",
        editor_print_now: "Print A4 Document",

        // QR Upload
        qr_modal_title: "Mobile Quick Print (QR Code)",
        qr_modal_subtitle: "Scan with your Smartphone camera (iOS / iPadOS / Android) to upload and print instantly",
        qr_close: "Close",

        // Kiosk & Admin
        kiosk_title: "PrintQ Kiosk",
        kiosk_subtitle: "Touch screen terminal for approving & releasing print jobs",
        approve: "Approve",
        deny: "Deny",
        all_clear: "All clear!",
        no_pending_jobs: "No pending print jobs. Waiting for new jobs...",
        kiosk_qr_title: "Scan QR for Smartphone Printing",
        kiosk_qr_desc: "Scan with your smartphone camera on the Internal Network to upload files or edit A4 documents directly.",
        done: "Done!",
        denied: "Denied",
        admin_jobs_tab: "All Jobs",
        admin_keys_tab: "API Keys",
        admin_devices_tab: "Device Mappings",
        admin_emails_tab: "Email Mappings",
        admin_kiosks_tab: "Kiosk Devices",
        create_api_key: "Create API Key",
        register_kiosk: "Register Kiosk Device",

        // Notifications
        job_released_success: "Job released for printing successfully!",
        job_cancelled_success: "Job cancelled successfully!",
        job_claimed_success: "Job claimed successfully!",
        confirm_action: "Are you sure you want to proceed?"
    },
    th: {
        // General & Brand
        brand_name: "PrintQ",
        brand_tagline: "ระบบจัดการคิวพิมพ์เอกสารระดับองค์กร",
        dashboard: "แผงควบคุมหลัก",
        upload_print: "อัปโหลดและสั่งพิมพ์",
        a4_editor: "เครื่องมือพิมพ์ A4 ด่วน",
        qr_mobile_print: "พิมพ์ผ่าน QR มือถือ",
        admin_panel: "ผู้ดูแลระบบ",
        kiosk_mode: "โหมดตู้คีออส",
        api_docs: "คู่มือ API",
        logout: "ออกจากระบบ",
        welcome: "ยินดีต้อนรับ",
        status: "สถานะ",
        online: "ออนไลน์",
        offline: "ออฟไลน์",

        // Landing & Auth
        landing_title: "ระบบจัดการการพิมพ์อัจฉริยะสำหรับองค์กร",
        landing_subtitle: "รวมคิวพิมพ์เอกสารสำหรับ Windows, Mac, Linux, iOS, iPadOS & Android พร้อม Authentik SSO และ Active Directory",
        login_with_echostory: "เข้าสู่ระบบด้วย EchoStory",
        login_with_ad: "เข้าสู่ระบบด้วย Active Directory",
        ad_username: "ชื่อผู้ใช้ AD",
        ad_password: "รหัสผ่าน",
        login_btn: "เข้าสู่ระบบ",
        ad_auth_title: "เข้าสู่ระบบด้วย Active Directory",
        sso_auth_title: "เข้าสู่ระบบด้วย Authentik SSO",
        quick_start_desc: "สแกน QR Code เพื่อสั่งพิมพ์จากสมาร์ทโฟน หรือเข้าสู่ระบบเพื่อจัดการคิวพิมพ์",

        // Dashboard & Jobs
        my_print_jobs: "งานพิมพ์ของฉัน",
        unclaimed_jobs: "งานพิมพ์ที่ยังไม่ได้อ้างสิทธิ์",
        no_jobs_found: "ไม่พบงานพิมพ์ในคิวขณะนี้",
        no_unclaimed_jobs: "ไม่มีงานพิมพ์ที่ยังไม่ได้อ้างสิทธิ์",
        job_id: "รหัสงานพิมพ์",
        filename: "ชื่อไฟล์",
        submitted_by: "ผู้สั่งพิมพ์",
        pages: "จำนวนหน้า",
        size: "ขนาด",
        submitted_at: "เวลาสั่งพิมพ์",
        actions: "การจัดการ",
        release_print: "อนุมัติพิมพ์เอกสาร",
        cancel: "ยกเลิกงานพิมพ์",
        claim_job: "อ้างสิทธิ์งานพิมพ์",
        claim_desc: "งานพิมพ์ผ่าน AirPrint / Mopria หรืออุปกรณ์พกพาสามารถกดอ้างสิทธิ์ได้ที่นี่",
        printer_status_title: "สถานะเครื่องพิมพ์",
        printer_ready: "เครื่องพิมพ์พร้อมใช้งาน",
        printer_offline: "เครื่องพิมพ์ออฟไลน์ หรือหยุดทำงาน",
        printer_busy: "กำลังดำเนินการพิมพ์",

        // Upload & Print
        upload_title: "อัปโหลดและสั่งพิมพ์เอกสาร",
        upload_subtitle: "รองรับไฟล์ PDF, PNG, JPG, JPEG, WEBP, DOCX, DOC, TXT",
        drag_drop_text: "ลากและวางไฟล์ที่นี่ หรือคลิกเพื่อเลือกไฟล์",
        copies: "จำนวนสำเนา",
        color_mode: "โหมดสี",
        color_full: "พิมพ์สี",
        color_bw: "ขาว-ดำ (ขาวดำ)",
        duplex_mode: "รูปแบบการพิมพ์",
        duplex_single: "พิมพ์หน้าเดียว",
        duplex_two: "พิมพ์สองหน้า (Duplex)",
        page_range: "ช่วงหน้า (ไม่ระบุ = พิมพ์ทั้งหมด)",
        page_range_help: "ตัวอย่าง: 1-5, 8, 11-13",
        submit_print_job: "ส่งงานพิมพ์เข้าคิว",

        // A4 Quick Editor
        editor_title: "เครื่องมือแก้ไข A4 แบบเบา",
        editor_subtitle: "สร้างข้อความ ใส่รูปภาพ จัดรูปแบบ และสั่งพิมพ์เอกสารขนาด A4 ได้ทันที",
        office_editor: "เครื่องมือแก้ไข Collabora Office",
        office_editor_desc: "ใช้ Writer แบบเต็มรูปแบบ รองรับการจัดรูปอักษรไทยและบันทึกอัตโนมัติ",
        new_document: "สร้างเอกสารใหม่",
        open_document: "เปิดไฟล์ ODT/DOCX",
        document_title: "ชื่อเอกสาร",
        size_normal: "ปกติ",
        size_medium: "กลาง",
        size_large: "ใหญ่",
        size_heading: "หัวข้อ",
        size_title: "ชื่อเรื่อง",
        editor_default_heading: "เอกสารด่วน",
        editor_default_body: "เริ่มพิมพ์เนื้อหาเอกสารที่นี่...",
        editor_heading_placeholder: "กรอกหัวข้อเอกสาร...",
        editor_body_placeholder: "พิมพ์เนื้อหาเอกสารของคุณที่นี่...",
        editor_font_size: "ขนาดตัวอักษร",
        editor_align_left: "ชิดซ้าย",
        editor_align_center: "กึ่งกลาง",
        editor_align_right: "ชิดขวา",
        editor_bold: "ตัวหนา",
        editor_italic: "ตัวเอียง",
        editor_insert_image: "แทรกรูปภาพ",
        editor_clear: "ล้างข้อความ",
        editor_print_now: "ส่งพิมพ์เอกสาร A4",

        // QR Upload
        qr_modal_title: "สั่งพิมพ์ด่วนผ่านสมาร์ทโฟน (QR Code)",
        qr_modal_subtitle: "ใช้กล้องสมาร์ทโฟน (iOS / iPadOS / Android) สแกนเพื่ออัปโหลดไฟล์และสั่งพิมพ์ได้ทันที",
        qr_close: "ปิด",

        // Kiosk & Admin
        kiosk_title: "โหมดตู้คีออส PrintQ",
        kiosk_subtitle: "หน้าจอสัมผัสสำหรับอนุมัติและปล่อยงานพิมพ์หน้าเครื่อง",
        approve: "อนุมัติ",
        deny: "ปฏิเสธ",
        all_clear: "เรียบร้อยแล้ว!",
        no_pending_jobs: "ไม่มีงานพิมพ์ที่รอดำเนินการ กำลังรอคิวพิมพ์ใหม่...",
        kiosk_qr_title: "สแกน QR Code เพื่อสั่งพิมพ์ผ่านสมาร์ทโฟน",
        kiosk_qr_desc: "ใช้กล้องสมาร์ทโฟนสแกนบนเครือข่ายภายใน เพื่ออัปโหลดไฟล์หรือสร้างเอกสาร A4 สั่งพิมพ์ได้ทันที",
        done: "สำเร็จ!",
        denied: "ปฏิเสธแล้ว",
        admin_jobs_tab: "งานพิมพ์ทั้งหมด",
        admin_keys_tab: "คีย์ API",
        admin_devices_tab: "การจับคู่อุปกรณ์",
        admin_emails_tab: "การจับคู่อีเมล",
        admin_kiosks_tab: "อุปกรณ์ตู้คีออส",
        create_api_key: "สร้างคีย์ API",
        register_kiosk: "ลงทะเบียนตู้คีออส",

        // Notifications
        job_released_success: "อนุมัติงานพิมพ์เรียบร้อยแล้ว!",
        job_cancelled_success: "ยกเลิกงานพิมพ์เรียบร้อยแล้ว!",
        job_claimed_success: "อ้างสิทธิ์งานพิมพ์เรียบร้อยแล้ว!",
        confirm_action: "คุณแน่ใจหรือไม่ว่าต้องการดำเนินการต่อ?"
    }
};

/**
 * Get current language (default 'en')
 */
function getCurrentLang() {
    return localStorage.getItem('pq_lang') || 'en';
}

/**
 * Switch language and update DOM
 */
function setLanguage(lang) {
    if (!translations[lang]) lang = 'en';
    localStorage.setItem('pq_lang', lang);
    document.cookie = `pq_lang=${lang}; path=/; max-age=31536000; SameSite=Lax`;

    const dict = translations[lang];
    document.documentElement.lang = lang;

    // Translate elements with data-i18n attribute
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (dict[key]) {
            el.textContent = dict[key];
        }
    });

    // Translate placeholders
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        if (dict[key]) {
            el.placeholder = dict[key];
        }
    });

    // Translate starter content until the user edits it; never overwrite their work.
    document.querySelectorAll('[data-i18n-initial]').forEach(el => {
        const key = el.getAttribute('data-i18n-initial');
        if (!el.dataset.userEdited && dict[key]) el.textContent = dict[key];
        if (!el.dataset.i18nBound) {
            el.addEventListener('input', () => { el.dataset.userEdited = 'true'; });
            el.dataset.i18nBound = 'true';
        }
    });

    // Translate element titles
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
        const key = el.getAttribute('data-i18n-title');
        if (dict[key]) {
            el.title = dict[key];
        }
    });

    // Update active state in language selector UI
    const langLabel = document.getElementById('currentLangLabel');
    if (langLabel) {
        langLabel.innerHTML = lang === 'th' ? '🇹🇭 TH' : '🇺🇸 EN';
    }
}

/**
 * Get localized string by key
 */
function t(key, defaultVal = '') {
    const lang = getCurrentLang();
    return (translations[lang] && translations[lang][key]) || defaultVal || key;
}

// Auto initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    setLanguage(getCurrentLang());
});
