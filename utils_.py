import os
import platform
import re
from datetime import timedelta, datetime
from pathlib import Path

DEBUG = False
islinux = platform.system() == 'Linux'
VERSION = '2.0.0'


def _exc(cmd):
	print(f'executing: "{cmd}"')
	
	res = os.popen(cmd).read()
	if DEBUG:
		print(res)
	
	if 'Done Saving Data' in res:
		return True
	return False


def get_data(
		addr_exe: Path,
		addr_ini: Path,
		addr_dest: Path,
		time_start: datetime,
		time_end: datetime = None,
		with_header_data=False,
		ensure_file=False
):
	if time_end is None:
		# set the end of day
		time_end = (time_start + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
	
	addr_dest.mkdir(exist_ok=True)
	addr_dest = Path(
		f'{addr_dest / ("out." + time_start.strftime("%Y%m%d_%H%M"))}.csv.tmp')
	
	while time_start < time_end:
		if _exc(
				f'{"wine" if islinux else ""} {addr_exe} '
				f'-w {addr_ini} -o "{addr_dest}" {"" if with_header_data else "-n"} -T '
				f'{time_start.strftime("%m%d%y_%H%M")} {int((time_end - time_start).total_seconds() / 60)}'
		):
			return addr_dest
		
		print(f'could not find {time_start}')
		time_start += timedelta(minutes=1)
	
	if ensure_file:
		open(addr_dest, 'w').close()
		return addr_dest


def _prepare_convert(
		addr_file: Path,
		addr_dest: Path = None,
		addr_conf: Path = None,
		addr_exe: Path = None,
		addr_ini: Path = None,
		print_=print,
):
	# region check inputs
	if not (addr_file.exists() and addr_file.is_file()):
		print_('err', f'not found or not a file: {addr_file}')
		return
	
	addr_base = Path(os.path.abspath(__file__)).parent
	addr_dest = addr_dest or addr_base / 'output'
	addr_conf = addr_conf or addr_base / 'conf'
	addr_exe = addr_exe or addr_base / 'drf2txt.exe'
	addr_ini = addr_ini or addr_conf / 'Winsdr.ini'
	
	if not addr_dest.exists():
		os.makedirs(addr_dest, exist_ok=True)
	
	if not (addr_conf.exists() and addr_conf.is_dir()):
		print_('err', f'not found or not a directory: {addr_conf}')
		return
	if not (addr_exe.exists() and addr_exe.is_file()):
		print_('err', f'not found or not a file: {addr_exe}')
		return
	if not (addr_ini.exists() and addr_ini.is_file()):
		print_('err', f'not found or not a file: {addr_ini}')
		return
	# endregion
	
	# region get file date from file name
	try:
		file_datetime = re.findall('sys\d\.(\d{8})\.dat', addr_file.name)[0]
		file_datetime = datetime(int(file_datetime[:4]), int(file_datetime[4: 6]), int(file_datetime[6:]), 0, 1, 0, 0)
	except:
		print_('err', f'file name must be like "sys1.20210101.dat": {addr_file}')
		return
	
	# endregion
	
	# region normalize .ini file
	with open(addr_ini, 'r') as f:
		ini_data_org = f.read()
	
	ini_data = []
	for line in ini_data_org.strip().split('\n'):
		if line.startswith('RecordPath='):
			line = f'RecordPath={addr_file.parent}' + ("/" if islinux else "\\")
		if line.startswith('ChanFile'):
			b, a = line.split('=')
			line = f'{b}={addr_conf / a}'
		
		ini_data.append(line)
	ini_data = '\n'.join(ini_data)
	addr_ini = Path(f'{addr_ini}.tmp')
	with open(addr_ini, 'w') as f:
		f.write(ini_data)
	
	# endregion
	
	return addr_file, addr_dest, addr_conf, addr_exe, addr_ini, file_datetime


def convert(
		addr_file: Path,
		addr_dest: Path = None,
		addr_conf: Path = None,
		addr_exe: Path = None,
		addr_ini: Path = None,
		print_=print,
		**kwargs
):
	addr_file, addr_dest, addr_conf, addr_exe, addr_ini, file_datetime = _prepare_convert(
		addr_file, addr_dest, addr_conf, addr_exe, addr_ini, print_)
	
	print_('succ', 'translating ...')
	addr_dest = get_data(addr_exe, addr_ini, addr_dest, file_datetime, **kwargs)
	if addr_dest is None:
		print_('err', f'could not get any data from {addr_file}')
		return
	else:
		new = addr_dest.parent / addr_dest.name.replace('.tmp', '')
		if new.exists():
			os.remove(new)
		addr_dest = addr_dest.rename(new)
	
	print_('succ', 'translated')
	
	# return file path
	return addr_dest


def convert_24(
		addr_file: Path,
		addr_dest: Path = None,
		addr_conf: Path = None,
		addr_exe: Path = None,
		addr_ini: Path = None,
		print_=print,
		**kwargs
):
	addr_file, addr_dest, addr_conf, addr_exe, addr_ini, file_datetime = _prepare_convert(
		addr_file, addr_dest, addr_conf, addr_exe, addr_ini, print_)
	
	addr_dest = addr_dest / file_datetime.strftime("%Y-%m-%d")
	
	tommorrow = (file_datetime + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
	time_end = (file_datetime + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
	time_start = file_datetime
	
	while time_start < tommorrow:
		print_('succ', f'%{int(100 * ((time_start.hour + 1) / 24))} translating ...')
		addr_output = get_data(addr_exe, addr_ini, addr_dest, time_start, time_end, ensure_file=True, **kwargs)
		
		new = addr_output.parent / addr_output.name.replace('.tmp', '')
		if new.exists():
			os.remove(new)
		addr_output = addr_output.rename(new)
		
		yield addr_output
		
		time_start = (time_start + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
		time_end = time_start + timedelta(hours=1)
