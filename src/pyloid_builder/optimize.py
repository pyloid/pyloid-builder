import os
import shutil
import time
import fnmatch
from pathlib import Path
from typing import List, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.layout import Layout


def parse_spec_file(spec_file: str) -> Tuple[List[str], List[str]]:
	"""
	Parse spec file to extract include and exclude patterns.

	Parameters
	----------
	spec_file : str
	    Path to the spec file containing patterns.

	Returns
	-------
	Tuple[List[str], List[str]]
	    (include_patterns, exclude_patterns)
	"""
	include_patterns = []
	exclude_patterns = []

	spec_path = Path(spec_file)
	if not spec_path.exists():
		raise FileNotFoundError(f"Spec file not found: {spec_file}")

	with open(spec_path, 'r', encoding='utf-8') as f:
		for line in f:
			line = line.strip()
			if not line or line.startswith('#'):
				continue  # Skip empty lines and comments

			if line.startswith('!'):
				exclude_patterns.append(line[1:])  # Remove '!' prefix
			else:
				include_patterns.append(line)

	return include_patterns, exclude_patterns


def optimize(base_path: str, spec_file: str):
	"""
	Optimize PyInstaller build output by removing unnecessary files based on spec file.

	Parameters
	----------
	base_path : str
	    Base path containing the build output (_internal folder).
	spec_file : str
	    Path to the spec file containing removal patterns.
	"""
	# Parse spec file
	include_patterns, exclude_patterns = parse_spec_file(spec_file)

	console = Console()

	# Target directory for optimization
	target_dir = Path(base_path)

	# Get terminal width
	terminal_width = console.size.width

	# Dynamically calculate left info panel width (50% of total width, minimum 40)
	info_panel_width = max(40, int(terminal_width * 0.5))

	def get_size_info(path: Path) -> Tuple[int, int, int]:
		"""Get size information for a path (total size, file count, directory count)"""
		total_size = 0
		file_count = 0
		dir_count = 0

		if path.is_file():
			total_size = path.stat().st_size
			file_count = 1
		elif path.is_dir():
			for item in path.rglob('*'):
				if item.is_file():
					try:
						total_size += item.stat().st_size
						file_count += 1
					except OSError:
						pass
				elif item.is_dir():
					dir_count += 1
			dir_count += 1  # Include current directory

		return total_size, file_count, dir_count

	def format_size(size_bytes: int) -> str:
		"""Format bytes into human-readable format"""
		if size_bytes == 0:
			return '0 B'
		for unit in ['B', 'KB', 'MB', 'GB']:
			if size_bytes < 1024.0:
				return f'{size_bytes:.1f} {unit}'
			size_bytes /= 1024.0
		return f'{size_bytes:.1f} GB'

	# Format patterns for display
	def format_patterns(include_patterns: List[str], exclude_patterns: List[str]) -> str:
		all_patterns = []
		all_patterns.extend(f'[red]DEL {p}[/red]' for p in include_patterns)  # 삭제 패턴
		all_patterns.extend(f'[green]KEEP {p}[/green]' for p in exclude_patterns)  # 유지 패턴

		if not all_patterns:
			return 'None'

		formatted_lines = []
		current_line = ''
		max_line_length = max(30, info_panel_width - 10)

		for item in all_patterns:
			if len(current_line) + len(item) + 2 <= max_line_length:
				current_line += (', ' + item) if current_line else item
			else:
				if current_line:
					formatted_lines.append(current_line)
				current_line = item

		if current_line:
			formatted_lines.append(current_line)

		return '\n'.join(formatted_lines)

	# Info panel content - converted to function for dynamic updates
	def create_info_panel(processed=0, total_size_saved=0, current_item=''):
		formatted_list = format_patterns(include_patterns, exclude_patterns)
		total_patterns = len(include_patterns) + len(exclude_patterns)
		progress_percent = int((processed / total_patterns) * 100) if total_patterns else 0

		panel_content = (
			f'[bold cyan]Target Directory:[/bold cyan]\n[dim]{target_dir}[/dim]\n\n'
			f'[bold cyan]Spec File:[/bold cyan]\n[dim]{spec_file}[/dim]\n\n'
			f'[bold cyan]Patterns ({total_patterns} items):[/bold cyan]\n{formatted_list}\n\n'
			f'[bold cyan]Progress:[/bold cyan] {processed}/{total_patterns} ({progress_percent}%)\n'
			f'[bold cyan]Space Saved:[/bold cyan] {format_size(total_size_saved)}\n'
		)

		if current_item:
			panel_content += f'[bold cyan]Processing:[/bold cyan] {current_item}'

		return Panel(
			panel_content,
			title='[bold blue]Optimization Progress[/bold blue]',
			border_style='blue',
			width=info_panel_width,
		)

	# Create initial info panel
	info_panel = create_info_panel()

	# Text object for logs
	log_text = Text('', style='dim white')
	log_panel = Panel(
		log_text, title='[bold green]Optimization Log[/bold green]', border_style='green'
	)

	# Create layout
	layout = Layout()
	layout.split_row(
		Layout(info_panel, name='info', size=info_panel_width), Layout(log_panel, name='log')
	)

	# Layout update function
	def update_layout(processed=0, total_size_saved=0, current_item=''):
		layout['info'].update(create_info_panel(processed, total_size_saved, current_item))

	log_lines = []
	max_log_lines = console.size.height - 6  # Maximum lines considering panel height

	def update_log(new_line: str, style: str = 'white'):
		"""Update log text with scrolling support"""
		log_lines.append(Text(new_line, style=style))
		if len(log_lines) > max_log_lines:
			del log_lines[0]

		log_text.truncate(0)  # Clear existing text
		for line in log_lines:
			log_text.append_text(line)
			log_text.append('\n')

	try:
		if not target_dir.is_dir():
			console.print(f'\n[bold red]ERROR: Target directory not found.[/bold red]')
			console.print(f'[dim]Path: {target_dir}[/dim]')
			raise FileNotFoundError(f"Target directory '{target_dir}' does not exist.")

		console.print('[bold blue]>>> Starting optimization...[/bold blue]\n')

		# Initialize statistics variables
		start_time = time.time()
		removed_count = 0
		not_found_count = 0
		total_removed_size = 0
		total_removed_files = 0
		total_removed_dirs = 0
		error_count = 0

		# Find all files and directories to process
		items_to_remove = []

		def expand_double_star(pattern: str) -> List[str]:
			"""Expand ** patterns into multiple fnmatch patterns"""
			if '**' not in pattern:
				return [pattern]

			parts = pattern.split('**', 1)
			if len(parts) != 2:
				return [pattern]

			prefix, suffix = parts
			prefix = prefix.rstrip('/')
			suffix = suffix.lstrip('/')

			# Generate patterns for different depths (up to depth 10)
			patterns = []
			for depth in range(10):  # Limit depth to prevent infinite expansion
				if prefix and suffix:
					# Pattern like "dir/**/*.ext"
					middle = '/*' * depth
					patterns.append(f"{prefix}{middle}/{suffix}")
					patterns.append(f"{prefix}{middle}{suffix}")  # Also match files directly
				elif prefix:
					# Pattern like "dir/**/*"
					middle = '/*' * depth
					patterns.append(f"{prefix}{middle}/*")
					patterns.append(f"{prefix}{middle}")
				elif suffix:
					# Pattern like "**/*.ext" - match at any depth
					middle = '/*' * depth
					patterns.append(f"{middle}/{suffix}")
					patterns.append(f"{middle}{suffix}")

			return patterns

		def matches_pattern(path_str: str, pattern: str) -> bool:
			"""Check if path matches pattern using expanded fnmatch patterns"""
			expanded_patterns = expand_double_star(pattern)
			return any(fnmatch.fnmatch(path_str, p) for p in expanded_patterns)

		for item in target_dir.rglob('*'):
			if not item.exists():  # Skip if item was already deleted
				continue

			relative_path = item.relative_to(target_dir)
			path_str = str(relative_path)

			# Check if item matches any include pattern
			matches_include = any(matches_pattern(path_str, pattern) for pattern in include_patterns)

			# Check if item matches any exclude pattern
			matches_exclude = any(matches_pattern(path_str, pattern) for pattern in exclude_patterns)

			# Include if matches include pattern and doesn't match exclude patterns
			if matches_include and not matches_exclude:
				items_to_remove.append(item)

		with Live(
			layout, console=console, refresh_per_second=10, vertical_overflow='visible'
		) as live:
			total_items = len(items_to_remove)

			for i, item_path in enumerate(items_to_remove):
				relative_path = item_path.relative_to(target_dir)

				# Update info panel
				update_layout(i, total_removed_size, str(relative_path))

				# Add artificial delay for visual effect
				time.sleep(0.05)

				try:
					# Calculate size before removal
					size_before, files_before, dirs_before = get_size_info(item_path)

					if item_path.is_file():
						item_path.unlink()
						log_message = f'[OK] Removed File: {relative_path} ({format_size(size_before)})'
						update_log(log_message, 'green')
						total_removed_files += 1
					elif item_path.is_dir():
						shutil.rmtree(item_path)
						log_message = f'[OK] Removed Dir:  {relative_path} ({format_size(size_before)}, {files_before} files)'
						update_log(log_message, 'green')
						total_removed_dirs += 1
						total_removed_files += files_before

					removed_count += 1
					total_removed_size += size_before

					# Update info panel (reflect progress)
					update_layout(i + 1, total_removed_size)

				except OSError as e:
					log_message = f'[ERROR] Error removing {relative_path}: {e}'
					update_log(log_message, 'bold red')
					error_count += 1
					# Update info panel (reflect progress)
					update_layout(i + 1, total_removed_size)

				live.update(layout)

			# Final results update
			end_time = time.time()
			elapsed_time = end_time - start_time

			update_log('\n' + '=' * 30, 'dim')
			update_log('Optimization Complete!', 'bold magenta')
			update_log('=' * 30, 'dim')

			# Display detailed statistics
			update_log(f'Processing Time: {elapsed_time:.1f}s', 'cyan')
			update_log(f'Space Saved: {format_size(total_removed_size)}', 'green')
			update_log(
				f'Items Removed: {removed_count} ({total_removed_files} files, {total_removed_dirs} dirs)',
				'green',
			)
			if error_count > 0:
				update_log(f'Errors: {error_count}', 'red')

			update_log('=' * 30, 'dim')
			update_log('Optimization successful!', 'bold green')

			log_panel.border_style = 'green'
			log_panel.title = '[bold green][COMPLETE] Optimization Complete[/bold green]'

			# Final info panel update (completion status)
			total_patterns = len(include_patterns) + len(exclude_patterns)
			update_layout(total_patterns, total_removed_size, 'Complete!')
			live.update(layout)

		console.print('\n[bold green]Your application has been optimized![/bold green]')
		console.print(f'[dim]Space saved: {format_size(total_removed_size)}[/dim]')
		console.print(f'[dim]Processing time: {elapsed_time:.1f} seconds[/dim]')
		console.print(f'[dim]Total items processed: {removed_count + error_count}[/dim]')

	except Exception as e:
		console.print(f'\n[bold red]An unexpected error occurred: {str(e)}[/bold red]')
		# When Live is active, panel state changes are difficult, so only console output here
		raise


if __name__ == '__main__':
	# --- Test Example ---
	# 1. Create dummy build folders and files
	app_name = 'MyApp'
	dist_path = 'dist'
	internal_path = os.path.join(dist_path, app_name, '_internal')
	spec_file_path = 'test_optimize.spec'

	print('Creating dummy build files for testing...')
	os.makedirs(internal_path, exist_ok=True)

	files_to_create = [
		'Qt5Core.dll',
		'Qt5Gui.dll',
		'libEGL.dll',
		'tcl/tcl8.6/init.tcl',
		'tk/tk8.6/tk.tcl',
		'tcl/tcl8.6/encoding/ascii.enc',
		'tk/tk8.6/images/logo.gif',
		'ucrtbase.dll',
		'python3.dll',
		'useless_temp_file.tmp',
	]
	for f in files_to_create:
		p = os.path.join(internal_path, f)
		os.makedirs(os.path.dirname(p), exist_ok=True)
		with open(p, 'w') as fp:
			fp.write('dummy content')
	print('Dummy files created.')

	# 2. Create spec file with patterns
	spec_content = '''# Test optimization spec file
# Include patterns
tcl/**/*
tk/**/*
*.dll
libEGL.dll
useless_temp_file.tmp

# Exclude patterns
!tcl/tcl8.6/init.tcl
!python3.dll
'''

	with open(spec_file_path, 'w') as f:
		f.write(spec_content)
	print(f'Spec file created: {spec_file_path}\n')

	# 3. Run optimization function
	try:
		optimize(base_path=internal_path, spec_file=spec_file_path)
	except Exception as e:
		print(f'Optimization failed: {e}')

