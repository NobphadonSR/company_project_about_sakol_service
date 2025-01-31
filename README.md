# ระบบจัดการการแก้ปัญหาจากลูกค้า

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
    ```bash
    python -m venv venv
    ```
    ```bash
    source venv/bin/activate
    ```
    ```bash
    venv\Scripts\activate
    ```

2. ติดตั้ง Dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3. ตั้งค่าฐานข้อมูล PostgreSQL:
    ```bash
    createdb electrical_crm_db
    ```

4. ทำการ Migrate ฐานข้อมูล:
    ```bash
    python manage.py migrate
    ```

5. สร้าง Superuser:
    ```bash
    python manage.py createsuperuser
    ```

6. รัน Development Server:
    ```bash
    python manage.py runserver
    ```

## โครงสร้างโปรเจกต์

- electrical_crm/
- accounts/
- service/
- static/
- media/
- templates/
- electrical_crm/

## การตั้งค่าสำคัญ

- **ภาษา:** Thai (th)
- **Timezone:** Asia/Bangkok
- **Static Files:** /static/
- **Media Files:** /media/
- **File Upload Limit:** 6MB

## ความปลอดภัย

- CSRF Protection
- XSS Protection
- Content Type Nosniff
- X-Frame-Options
- Secure File Upload Handling

## การพัฒนาต่อ

- [ ] เพิ่มระบบแจ้งเตือนผ่าน LINE
- [ ] ระบบออกรายงานในรูปแบบ PDF
- [ ] ระบบคำนวณค่าบริการอัตโนมัติ
- [ ] ระบบติดตามสถานะงานแบบ Real-time

## หมายเหตุ

โปรดระวัง: ไม่ควรใช้ค่า `SECRET_KEY` และ API Key ที่แสดงในโค้ดในการใช้งานจริง ควรเก็บไว้ใน environment variables