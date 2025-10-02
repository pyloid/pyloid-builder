import os
import shutil
import time
import glob
from typing import List, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.layout import Layout


def optimize(path: str, remove_list: List[str]):
	"""
	Optimize PyInstaller build output by removing unnecessary files.

	Parameters
	----------
	path : str
	    app build output path.
	remove_list : List[str]
	    List of files or folders to remove. Supports wildcards (*, ?).
	"""
	console = Console()

	# Target directory for optimization
	target_dir = os.path.join(path, "_internal")

	# Get terminal width
	terminal_width = console.size.width

	# Dynamically calculate left info panel width (50% of total width, minimum 40)
	info_panel_width = max(40, int(terminal_width * 0.5))

	def get_size_info(path: str) -> Tuple[int, int, int]:
		"""Get size information for a path (total size, file count, directory count)"""
		total_size = 0
		file_count = 0
		dir_count = 0

		if os.path.isfile(path):
			total_size = os.path.getsize(path)
			file_count = 1
		elif os.path.isdir(path):
			for root, dirs, files in os.walk(path):
				dir_count += len(dirs)
				for file in files:
					try:
						total_size += os.path.getsize(os.path.join(root, file))
						file_count += 1
					except OSError:
						pass
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

	# Format remove list for display
	def format_remove_list(items: List[str]):
		if not items:
			return 'None'

		formatted_lines = []
		current_line = ''
		max_line_length = max(30, info_panel_width - 10)

		for item in items:
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
		formatted_list = format_remove_list(remove_list)
		progress_percent = int((processed / len(remove_list)) * 100) if remove_list else 0

		panel_content = (
			f'[bold cyan]Target Directory:[/bold cyan]\n[dim]{target_dir}[/dim]\n\n'
			f'[bold cyan]Remove List ({len(remove_list)} items):[/bold cyan]\n{formatted_list}\n\n'
			f'[bold cyan]Progress:[/bold cyan] {processed}/{len(remove_list)} ({progress_percent}%)\n'
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
		if not os.path.isdir(target_dir):
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

		# Expand wildcard patterns
		expanded_remove_list = []
		for item in remove_list:
			if '*' in item or '?' in item:
				# For wildcard patterns, find matching files/folders
				pattern_path = os.path.join(target_dir, item)
				matches = glob.glob(pattern_path)
				if matches:
					# Convert to relative paths and add to list
					for match in matches:
						relative_path = os.path.relpath(match, target_dir)
						expanded_remove_list.append(
							(item, relative_path)
						)  # (original pattern, actual path)
				else:
					# Keep original pattern even if no matches (will be marked as not found)
					expanded_remove_list.append((item, item))
			else:
				# Add regular items as-is
				expanded_remove_list.append((item, item))

		with Live(
			layout, console=console, refresh_per_second=10, vertical_overflow='visible'
		) as live:
			total_items = len(expanded_remove_list)

			for i, (original_pattern, actual_path) in enumerate(expanded_remove_list):
				item_path = os.path.join(target_dir, actual_path)

				# Update info panel (show current item being processed - display original pattern)
				display_name = (
					f'{original_pattern} -> {actual_path}'
					if original_pattern != actual_path
					else actual_path
				)
				update_layout(i, total_removed_size, display_name)

				# Add artificial delay for visual effect
				time.sleep(0.05)

				if os.path.exists(item_path):
					try:
						# Calculate size before removal
						size_before, files_before, dirs_before = get_size_info(item_path)

						if os.path.isfile(item_path) or os.path.islink(item_path):
							os.remove(item_path)
							log_message = f'[OK] Removed File: {actual_path}'
							if original_pattern != actual_path:
								log_message += f' (matched by {original_pattern})'
							log_message += f' ({format_size(size_before)})'
							update_log(log_message, 'green')
							total_removed_files += 1
						elif os.path.isdir(item_path):
							shutil.rmtree(item_path)
							log_message = f'[OK] Removed Dir:  {actual_path}'
							if original_pattern != actual_path:
								log_message += f' (matched by {original_pattern})'
							log_message += f' ({format_size(size_before)}, {files_before} files)'
							update_log(log_message, 'green')
							total_removed_dirs += 1
							total_removed_files += files_before

						removed_count += 1
						total_removed_size += size_before

						# Update info panel (reflect progress)
						update_layout(i + 1, total_removed_size)

					except OSError as e:
						log_message = f'[ERROR] Error removing {actual_path}: {e}'
						if original_pattern != actual_path:
							log_message += f' (matched by {original_pattern})'
						update_log(log_message, 'bold red')
						error_count += 1
						# Update info panel (reflect progress)
						update_layout(i + 1, total_removed_size)
				else:
					log_message = f'[SKIP] Not found:    {actual_path}'
					if original_pattern != actual_path:
						log_message += f' (pattern: {original_pattern})'
					update_log(log_message, 'yellow')
					not_found_count += 1
					# 정보 패널 업데이트 (진행 상황 반영)
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
			update_log(f'Not Found: {not_found_count}', 'yellow' if not_found_count > 0 else 'dim')
			if error_count > 0:
				update_log(f'Errors: {error_count}', 'red')

			update_log('=' * 30, 'dim')
			update_log('Optimization successful!', 'bold green')

			log_panel.border_style = 'green'
			log_panel.title = '[bold green][COMPLETE] Optimization Complete[/bold green]'

			# Final info panel update (completion status)
			update_layout(len(remove_list), total_removed_size, 'Complete!')
			live.update(layout)

		console.print('\n[bold green]Your application has been optimized![/bold green]')
		console.print(f'[dim]Space saved: {format_size(total_removed_size)}[/dim]')
		console.print(f'[dim]Processing time: {elapsed_time:.1f} seconds[/dim]')
		console.print(
			f'[dim]Total items processed: {removed_count + not_found_count + error_count}[/dim]'
		)

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
	print('Dummy files created.\n')

	# 2. Define files to remove
	files_to_remove = [
		'tcl',  # Entire tcl folder
		'tk',  # Entire tk folder
		'*.dll',  # All dll files (wildcard pattern)
		'libEGL.dll',  # Specific file (duplicate test)
		'non_existent_file.dll',  # Non-existent file (test case)
	]

	# 3. Run optimization function
	try:
		optimize(name=app_name, distpath=dist_path, remove_list=files_to_remove)
	except Exception as e:
		print(f'Optimization failed: {e}')
	finally:
		# 4. Clean up dummy folders after testing
		if os.path.exists(dist_path):
			print('\nCleaning up dummy build files...')
			shutil.rmtree(dist_path)
			print('Cleanup complete.')
