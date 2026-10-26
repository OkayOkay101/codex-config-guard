# Codex Config Guard

[English](README.md) | ไทย

ระบบตรวจไวยากรณ์และกู้คืน `config.toml` ของ Codex บน Windows อัตโนมัติ โดยไม่ต้องเปิด Codex ก่อน
ไฟล์เป้าหมายคือ `%CODEX_HOME%\config.toml` หากตั้งตัวแปรไว้ มิฉะนั้นใช้ `%USERPROFILE%\.codex\config.toml`

## ติดตั้งแบบง่าย

ต้องมี Windows 10/11 และ [Python 3.11 ขึ้นไป](https://www.python.org/downloads/windows/) (ติ๊ก *Add python.exe to PATH* ตอนติดตั้ง)

1. ดาวน์โหลด: กด **Code → Download ZIP** บนหน้า GitHub แล้วแตกไฟล์ไว้ในที่ถาวร เช่น `Documents\Codex Config Guard`
   (หรือ `git clone https://github.com/OkayOkay101/codex-config-guard.git`)
2. ดับเบิลคลิก **`Install.cmd`** — ตรวจ config ปัจจุบัน สำรองชุดแรก แล้วลงทะเบียน Task Scheduler ให้ทำงานทุกครั้งที่ล็อกอิน (ไม่ต้องใช้สิทธิ์ผู้ดูแลระบบ)
3. ดับเบิลคลิก **`Status.cmd`** เพื่อตรวจว่าทำงานแล้ว

> อย่าย้ายโฟลเดอร์หลังติดตั้ง หากย้ายให้รัน `Install.cmd` ใหม่
> config ปัจจุบันต้องเป็น TOML ที่ถูกต้องก่อนติดตั้ง มิฉะนั้นจะไม่ลงทะเบียนงาน

## ใช้งาน

| ทางลัด | คำสั่ง PowerShell (ในโฟลเดอร์เครื่องมือ) | หน้าที่ |
|---|---|---|
| `Status.cmd` | `.\Guard.ps1 status` | ตรวจไฟล์จริง จำนวนสำเนา และ heartbeat |
| — | `.\Guard.ps1 check` | ตรวจไวยากรณ์อย่างเดียว |
| ลากไฟล์ใส่ `Apply-Draft.cmd` | `.\Guard.ps1 apply C:\path\draft.toml` | ตรวจไฟล์ร่าง สำรอง แล้วแทนที่แบบ atomic |
| `Restore.cmd` | `.\Guard.ps1 restore` | คืนสำเนาล่าสุดที่ผ่านการตรวจ |

`apply` รักษา bytes ความคิดเห็น และรูปแบบขึ้นบรรทัดเดิม ไฟล์ร่างต้องเป็นคนละไฟล์กับ config จริง ส่วน `restore` จะไม่ย้อนรุ่นถ้าไฟล์ปัจจุบันตรงกับสำเนาล่าสุดอยู่แล้ว

ตัวเฝ้าดูใช้ `pythonw` (ไม่มีหน้าต่างคอนโซล) ตรวจทุก 2 วินาที และรอไฟล์นิ่งอย่างน้อย 3 วินาทีก่อนสำรองหรือกู้คืน

## การเขียนพาธ Windows ใน TOML

```toml
command = 'C:\Program Files\nodejs\node.exe'   # literal string ไม่ต้อง escape
```

หากใช้เครื่องหมายคำพูดคู่ ต้อง escape backslash (`\\`) ตัวแก้ไขที่รองรับ schema เพิ่มบรรทัดนี้ในไฟล์ร่างได้:

```toml
#:schema https://developers.openai.com/codex/config-schema.json
```

## ข้อมูลที่เก็บและความปลอดภัย

- `state/backups/` สำเนาที่ผ่านล่าสุด 20 รุ่น พร้อม SHA-256
- `state/quarantine/` ไฟล์เสียก่อนกู้คืน ไม่ลบอัตโนมัติ
- `state/events.jsonl` เวลา UTC ชนิดเหตุการณ์ hash และตำแหน่งผิดพลาด **ไม่มีเนื้อหา config** หมุน log เมื่อเกิน 2 MB
- `state/` จำกัดสิทธิ์เฉพาะผู้ใช้ที่ติดตั้ง SYSTEM และ Administrators เพราะสำเนาอาจมี API key หรือ token
- `state/`, `work/` และ `runtime.json` อยู่ใน `.gitignore` — **ห้ามแชร์หรือ commit โฟลเดอร์ `state/`**
- เครื่องมือไม่ติดต่อเครือข่าย ไม่แก้ชื่อโมเดล นโยบายสิทธิ์ หรือการตั้งค่า MCP

## จัดการงานเบื้องหลัง / ถอนการติดตั้ง

```powershell
Get-ScheduledTaskInfo -TaskName 'Codex Config Guard'
Stop-ScheduledTask    -TaskName 'Codex Config Guard'
Start-ScheduledTask   -TaskName 'Codex Config Guard'
Unregister-ScheduledTask -TaskName 'Codex Config Guard' -Confirm:$false   # ถอนการติดตั้ง
```

หลังถอนงาน หากยังต้องการสำเนาเดิม ให้เก็บ `state/backups/` ไว้ก่อนลบโฟลเดอร์

## ข้อจำกัด

- TOML ที่ถูกไวยากรณ์อาจยังมีค่าที่ Codex ไม่รองรับ
- เมื่อโปรแกรมอื่นเขียน config ตรง ๆ มีช่วงสั้น ๆ ก่อนกู้คืนที่ Codex อาจอ่านไฟล์เสียได้ ใช้ `apply` เพื่อตรวจก่อนแตะไฟล์จริง
- หากสำเนาทุกชุดเสีย จะไม่เขียนค่าเริ่มต้นทับ และตัวเฝ้าดูทำงานเฉพาะช่วงที่ผู้ใช้ล็อกอิน
- การแจ้งเตือนเป็น tray balloon ซึ่ง Windows อาจซ่อน ตรวจ `status` หรือ log ได้เสมอ

## เครื่องมือแนะนำ: Codex Sidebar Repair

หากปัญหาคือ **โปรเจกต์หรือการจัดกลุ่มแชตหายจาก sidebar ของ Codex desktop** (ข้อมูลยังอยู่ในฐานข้อมูล) แนะนำ
[Swih/codex-sidebar-repair](https://github.com/Swih/codex-sidebar-repair) — เครื่องมือกู้คืนแบบไม่เป็นทางการบน Windows (MIT License)

- ใช้ Node.js 24 ขึ้นไป ไม่มี dependency ไม่ต้องใช้สิทธิ์ผู้ดูแลระบบ
- `node repair-sidebar.cjs` ดูตัวอย่างโดยไม่แก้ไฟล์; ซ่อมจริงด้วย `--apply` หลังปิด Codex ทั้งหมด
- อาศัยรูปแบบข้อมูลภายในที่อาจเปลี่ยนตามเวอร์ชัน

Config Guard ดูแลไฟล์ตั้งค่า ส่วน Sidebar Repair ดูแลสถานะ sidebar ใช้ร่วมกันได้

## เอกสารเพิ่มเติม

- [สถาปัตยกรรมและลำดับการทำงาน](docs/ARCHITECTURE.th.md) · [Architecture (English)](docs/ARCHITECTURE.md)
- อ้างอิงการตั้งค่า Codex: https://learn.chatgpt.com/docs/config-file/config-reference

## ทดสอบ

```powershell
python -m unittest discover -v
```

การทดสอบใช้ไฟล์จำลองใน `work/` ไม่แตะ config จริง
