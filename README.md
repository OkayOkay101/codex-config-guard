# Codex Config Guard

ระบบตรวจไวยากรณ์และกู้คืน `C:\Users\Smart\.codex\config.toml` บน Windows โดยไม่ต้องเปิด Codex ก่อน

## ใช้งาน

เปิด PowerShell แล้วใช้คำสั่งต่อไปนี้ (ไฟล์ร่างต้องเป็นคนละไฟล์กับ config จริง):

```powershell
& 'C:\Users\Smart\Documents\Codex\Codex Config Guard\Guard.ps1' status
& 'C:\Users\Smart\Documents\Codex\Codex Config Guard\Guard.ps1' check
& 'C:\Users\Smart\Documents\Codex\Codex Config Guard\Guard.ps1' apply 'C:\path\draft.toml'
& 'C:\Users\Smart\Documents\Codex\Codex Config Guard\Guard.ps1' restore
```

`apply` ตรวจไฟล์ร่าง สำรองไฟล์เดิม แล้วแทนที่แบบ atomic พร้อมตรวจอ่านกลับ รักษา bytes ความคิดเห็น และรูปแบบขึ้นบรรทัดเดิม คำสั่ง `restore` คืนสำเนาล่าสุดที่ผ่าน TOML และ hash; หากไฟล์ปัจจุบันตรงสำเนาล่าสุดอยู่แล้ว จะไม่ย้อนรุ่นโดยพลการ

งาน Task Scheduler ชื่อ **Codex Config Guard** เริ่มเมื่อผู้ใช้ Smart เข้าสู่ Windows และเริ่มทันทีตอนติดตั้ง ใช้ pythonw จึงไม่มีหน้าต่างคอนโซล ตรวจทุก 2 วินาทีและรอไฟล์คงที่อย่างน้อย 3 วินาที ก่อนสำรองหรือกู้คืน หลีกเลี่ยงสำเนาขณะที่กำลังพิมพ์/เขียนไฟล์

## การตั้งค่าพาธ Windows

ใช้ literal string สำหรับพาธธรรมดา:

```toml
command = 'C:\Program Files\nodejs\node.exe'
```

หากใช้เครื่องหมายคู่ ต้อง escape backslash ให้ถูกต้อง อย่าแก้พาธทั้งหมดด้วยการแทนที่ข้อความแบบกว้าง

ตัวแก้ไขที่รองรับ TOML schema สามารถเพิ่มบรรทัดต่อไปนี้ในไฟล์ร่างได้ โดยระบบนี้ไม่ได้เพิ่มให้ไฟล์จริงอัตโนมัติ:

```toml
#:schema https://developers.openai.com/codex/config-schema.json
```

อ้างอิง: https://learn.chatgpt.com/docs/config-file/config-reference

## ตรวจสอบและสำรอง

- `state/backups/`: สำเนา TOML ที่ผ่านล่าสุด 20 รุ่น พร้อม metadata SHA-256; ไม่ใช้ไฟล์ backup เดิมของเครื่องโดยอัตโนมัติ
- `state/quarantine/`: ไฟล์เสียก่อนกู้คืน ไม่ลบอัตโนมัติ เพราะอาจต้องดึงการแก้ไขล่าสุดคืน
- `state/events.jsonl`: เวลา UTC, ชนิดเหตุการณ์, hash และตำแหน่งผิดพลาด ไม่มีเนื้อหา config; หมุน log เมื่อเกิน 2 MB
- `status`: ตรวจไฟล์จริง พร้อมจำนวนสำเนาที่ตรวจผ่านและ heartbeat ล่าสุด (`heartbeat_recent`); heartbeat ไม่ใช่หลักฐานว่าโมเดลหรือ MCP ทำงาน
- `state/` จำกัดสิทธิ์ให้ผู้ใช้ที่ติดตั้ง, SYSTEM และ Administrators เพราะสำเนาอาจมีข้อมูลลับ
- การแจ้งเตือนใช้ Windows tray balloon และอาจถูกซ่อนโดยการตั้งค่าการแจ้งเตือนของ Windows; ตรวจสถานะ/log ได้เสมอ

```powershell
Get-ScheduledTask -TaskName 'Codex Config Guard'
Get-ScheduledTaskInfo -TaskName 'Codex Config Guard'
Stop-ScheduledTask -TaskName 'Codex Config Guard'
Start-ScheduledTask -TaskName 'Codex Config Guard'
```

หากต้องการปิดถาวร ใช้ `Stop-ScheduledTask` แล้ว `Disable-ScheduledTask` สำหรับชื่อนี้ การถอนงานใช้ `Unregister-ScheduledTask -TaskName 'Codex Config Guard'` และเก็บสำเนาไว้ก่อนลบโฟลเดอร์เครื่องมือ

ติดตั้งซ้ำได้ด้วย `Install.ps1` จะสำรองนิยามงานเดิมที่เป็นของเครื่องมือนี้ก่อนเปลี่ยน ระบบไม่แก้ MCP หรือ TokenSave

## ขอบเขต

TOML ที่ถูกต้องอาจยังมีค่าที่ Codex ไม่รองรับ เครื่องมือไม่เปลี่ยนชื่อโมเดล นโยบายสิทธิ์ หรือการตั้งค่า MCP ให้เอง และไม่ติดต่อบริการภายนอก

เมื่อโปรแกรมอื่นเขียน config ตรง ยังมีช่วงสั้น ๆ ก่อนกู้คืนที่ Codex อาจอ่านไฟล์เสียได้ ตัวเฝ้าดูตรวจ hash ก่อนแทนที่และใช้ lock ระหว่างคำสั่งของเครื่องมือ แต่ไม่สามารถบังคับให้โปรแกรมอื่นถือ lock เดียวกัน จึงยังมีช่องว่างเล็กมากระหว่างตรวจ hash กับ atomic replace ใช้ `apply` เพื่อให้การบันทึกภายใต้เครื่องมือนี้ตรวจผ่านก่อนแตะไฟล์จริง

หากสำเนาทุกชุดเสีย จะไม่เขียนค่าเริ่มต้นทับ หากไฟล์ถูกล็อกหรือสิทธิ์ไม่พอจะบันทึกเหตุการณ์และลองใหม่ ตัวเฝ้าดูทำงานในช่วงที่ผู้ใช้ล็อกอิน ไม่ใช่บริการก่อนเข้าระบบ

## เครื่องมือแนะนำ: Codex Sidebar Repair

หากปัญหาไม่ใช่ `config.toml` แต่เป็น **โปรเจกต์หรือการจัดกลุ่มแชตหายจาก sidebar ของ Codex desktop** (ข้อมูลยังอยู่ในฐานข้อมูล) แนะนำ
[Swih/codex-sidebar-repair](https://github.com/Swih/codex-sidebar-repair) — เครื่องมือกู้คืนแบบไม่เป็นทางการบน Windows (MIT License)

- ต้องใช้ Node.js 24 ขึ้นไป ไม่มี dependency ไม่ต้องใช้สิทธิ์ผู้ดูแลระบบ
- โหมด preview (`node repair-sidebar.cjs`) ไม่แก้ไฟล์ใด ๆ; สั่งซ่อมจริงด้วย `--apply` หลังปิด Codex ทั้งหมด
- อ่าน `.codex-global-state.json` และ `state_5.sqlite` ใน `CODEX_HOME` และอาศัยรูปแบบภายในที่อาจเปลี่ยนตามเวอร์ชัน

ทั้งสองเครื่องมือทำงานเสริมกัน: Config Guard ดูแลไฟล์ตั้งค่า ส่วน Sidebar Repair ดูแลสถานะ sidebar

## เอกสารเพิ่มเติม

- [สถาปัตยกรรมและลำดับการทำงาน](docs/ARCHITECTURE.md)

## ทดสอบ

```powershell
Set-Location 'C:\Users\Smart\Documents\Codex\Codex Config Guard'
python -m unittest discover -v
```

การทดสอบสร้างไฟล์จำลองใน `work/` ไม่ทำให้ config จริงเสีย
