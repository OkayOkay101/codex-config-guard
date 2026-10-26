# สถาปัตยกรรม Codex Config Guard

## ส่วนประกอบ

| ไฟล์ | หน้าที่ |
|---|---|
| `guard.py` | แกนหลัก: ตรวจ TOML (`tomllib`), สำรอง, กู้คืน, เฝ้าดู (`watch`) และ CLI |
| `Guard.ps1` | ตัวเรียก `guard.py` ด้วย Python ที่ระบุใน `runtime.json` |
| `Install.ps1` | สร้าง `runtime.json` และลงทะเบียน Task Scheduler ชื่อ *Codex Config Guard* |
| `Verify-Installation.ps1` | ตรวจว่างาน, Python และไฟล์ config อยู่ในสภาพพร้อมใช้ |
| `Notify.ps1` | แสดง tray balloon เมื่อมีการกู้คืนหรือข้อผิดพลาด |
| `Status.cmd` / `Restore.cmd` / `Apply-Draft.cmd` | ทางลัดดับเบิลคลิก |
| `test_guard.py` | unit test ทำงานบนไฟล์จำลองใน `work/` |

## ลำดับการทำงาน

```
config.toml เปลี่ยน ──► รอไฟล์นิ่ง ≥ 3 วินาที ──► validate (tomllib)
                                              ├─ ผ่าน ─► สำรองลง state/backups (+ SHA-256)
                                              └─ ไม่ผ่าน ─► ย้ายไฟล์เสียไป state/quarantine
                                                          ─► ตรวจ hash ซ้ำ ─► atomic replace ด้วยสำเนาล่าสุดที่ผ่าน
```

- **Atomic write**: เขียนไฟล์ชั่วคราวในโฟลเดอร์เดียวกัน แล้ว `os.replace` จากนั้นอ่านกลับเพื่อยืนยัน hash
- **Lock**: `state/operation.lock` ป้องกันคำสั่งของเครื่องมือชนกัน; `state/watch.lock` กันตัวเฝ้าดูซ้อน
- **ความเป็นส่วนตัว**: log ไม่เก็บเนื้อหา config หรือข้อความจาก parser (อาจมีความลับ)
- **ข้อยกเว้น**: `ConfigError` (TOML เสีย), `ConflictError` (ไฟล์เปลี่ยนระหว่างทำงาน), `NoBackupError` (ไม่มีสำเนาที่ใช้ได้ — จะไม่เขียนค่าเริ่มต้นทับ)

## เป้าหมายคงที่

`TARGET` ถูกกำหนดตายตัวใน `guard.py` (`C:\Users\Smart\.codex\config.toml`) โดยตั้งใจ ไม่มีตัวเลือก override ใน CLI
หากใช้บนเครื่องอื่น ให้แก้ค่าคงที่นี้และพาธใน `README.md` ก่อนติดตั้ง
