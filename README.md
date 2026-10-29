# 몽글펫 - 작은 데스크톱 펫

Windows 작업 표시줄 바로 위에 작은 캐릭터만 보이는 데스크톱 펫입니다. 큰 창이나 상태 표시창은 기본으로 열리지 않습니다.

## 조작법
- 캐릭터는 작업 표시줄 위를 자동으로 걸어 다닙니다.
- 마우스 왼쪽 버튼으로 끌어 놓으면 중력에 따라 떨어지고, 작업 표시줄에 닿으면 주저앉았다 일어납니다.
- 캐릭터를 오른쪽 클릭하면 밥 주기, 놀아주기 외에 울어버리기, 잠 깬 뒤 체조하기, 파스타 댄스, 신나게 달리기, 꾸벅 인사하기, 폴짝 뛰기, 낮잠 등 행동 메뉴가 열립니다.
- 행동은 치이카와 애니메이션에서 기억에 남는 체조·춤·달리기·식사·인사 같은 장면에서 영감을 얻은 오리지널 미니 애니메이션이며, 공식 캐릭터 이미지나 장면을 그대로 복제하지 않습니다.
- 성장/경험치/코인/아이템과 상태는 `%APPDATA%\\MonglePet\\save.json`에 자동 저장됩니다.

## Windows EXE 직접 빌드
`build_exe.bat`를 실행하거나 아래 명령을 사용하세요.

```bat
python -m pip install --upgrade pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --windowed --name MonglePet monglepet.pyw
```

EXE는 `dist\\MonglePet.exe`에 생성됩니다.

## GitHub Actions로 빌드
저장소 루트에 `monglepet.pyw`를 올리고 `.github/workflows/build-windows.yml`을 유지한 뒤 Actions에서 `Build Windows EXE`를 실행합니다. 성공한 실행 기록의 Artifacts에서 `MonglePet-Windows-EXE`를 다운로드하세요.
