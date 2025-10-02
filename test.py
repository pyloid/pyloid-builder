from pyloid_builder.pyinstaller import pyinstaller

# PyInstaller 빌드
pyinstaller(
	'main.py',
	[
		'--name=test1',
		'--clean',
		'--noconfirm',
		'--onedir',
		'--add-data=./src:./src',
		'--add-data=./src:./src',
		'--add-data=./src:./src',
		'--add-data=./src:./src',
		'--add-data=./src:./src',
		'--windowed',
	],
)

# 기본 최적화 실행 (기본 불필요 파일들 제거)
# optimize("test1", "dist")

# 사용자 정의 제거 목록으로 최적화 실행 예시:
# custom_removal_list = [
#     "tcl",
#     "tk",
#     "test",
#     "Lib/site-packages/pip*",
#     "Lib/site-packages/setuptools*"
# ]
# optimize_with_custom_list("test1", "dist", custom_removal_list)
