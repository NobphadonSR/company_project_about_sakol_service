# sakol_service_crm_projects

ระบบจัดการงานบริการและซ่อมบำรุงอุปกรณ์ไฟฟ้า สำหรับบริษัทรับเหมาติดตั้งและซ่อมบำรุงระบบไฟฟ้า

## คุณสมบัติหลัก

- ระบบจัดการผู้ใช้งานแบบหลายระดับ (ลูกค้า, ช่างเทคนิค, ฝ่ายบริการ)
- ระบบแจ้งซ่อมและติดตั้งอุปกรณ์
- ระบบจัดการนัดหมายและติดตามงาน
- ระบบรายงานและสรุปผลการดำเนินงาน
- ระบบจัดการประกันสินค้าและบริการ
- ระบบอัพโหลดรูปภาพประกอบงาน

## เทคโนโลยีที่ใช้

- **Framework:** Django 5.1
- **Database:** PostgreSQL
- **Frontend:** Bootstrap 5
- **Form Handling:** Crispy Forms
- **Maps Integration:** Google Maps API, Leaflet and OpenStreetMap
- **File Upload:** Django File Upload System

## การติดตั้ง

1. สร้าง Virtual Environment:
    `python -m venv venv`
    `source venv/bin/activate # สำหรับ Linux/Mac`
    `venv\Scripts\activate # สำหรับ Windows`

2. ติดตั้ง Dependencies:
    `pip install -r requirements.txt`

3. ตั้งค่าฐานข้อมูล PostgreSQL:
    `createdb electrical_crm_db`

4. ทำการ Migrate ฐานข้อมูล:
    `python manage.py migrate`

5. สร้าง Superuser:
    `python manage.py createsuperuser`

6. รัน Development Server:
    `python manage.py runserver`

## โครงสร้างโปรเจกต์

`electrical_crm/`
├── accounts/            # แอพจัดการผู้ใช้งาน
├── service/            # แอพจัดการงานบริการ
├── static/            # ไฟล์ static (CSS, JS, Images)
├── media/             # ไฟล์ที่ผู้ใช้อัพโหลด
├── templates/         # เทมเพลตหลัก
├── electrical_crm/    # การตั้งค่าหลักของโปรเจกต์

## การตั้งค่าสำคัญ

- **ภาษา:** Thai (th)
- **Timezone:** Asia/Bangkok
- **Static Files:** /static/
- **Media Files:** /media/
- **File Upload Limit:** 5MB

## ความปลอดภัย

- CSRF Protection
- XSS Protection
- Content Type Nosniff
- X-Frame-Options
- Secure File Upload Handling

## API ที่ใช้

- Google Maps API สำหรับแสดงตำแหน่งที่ตั้ง

## การพัฒนาต่อ

- [ ] เพิ่มระบบแจ้งเตือนผ่าน LINE
- [ ] ระบบออกรายงานในรูปแบบ PDF
- [ ] ระบบคำนวณค่าบริการอัตโนมัติ
- [ ] ระบบติดตามสถานะงานแบบ Real-time

## หมายเหตุ

โปรดระวัง: ไม่ควรใช้ค่า `SECRET_KEY` และ API Key ที่แสดงในโค้ดในการใช้งานจริง ควรเก็บไว้ใน environment variables