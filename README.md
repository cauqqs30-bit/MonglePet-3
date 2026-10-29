# 몽글펫 - 투명 PNG 캐릭터 수정본

- 캐릭터를 고해상도 투명 PNG(`pet_hachiware.png`)로 표시하도록 변경했습니다.
- 투명 배경 창 위에 이미지의 알파 채널을 사용해 캐릭터가 사라지거나 도형이 깨져 보이는 문제를 줄였습니다.
- 상점 구매 완료 팝업을 없앴고, 상태창에 레벨 경험치 바를 표시합니다.
- 레벨에 따라 캐릭터 크기와 장식이 변합니다.

## Windows EXE 만들기
1. `monglepet.pyw`, `pet_hachiware.png`, `build_exe.bat` 파일을 같은 폴더에 둡니다.
2. `build_exe.bat`를 실행합니다.
3. 완성된 파일은 `dist\MonglePet.exe`에 생성됩니다.

GitHub Actions를 사용하는 경우 이 폴더의 모든 파일을 저장소에 올리고 Actions에서 `Build Windows EXE`를 실행하세요.

참고: EXE는 Windows에서 직접 실행 테스트되지 않았습니다.
