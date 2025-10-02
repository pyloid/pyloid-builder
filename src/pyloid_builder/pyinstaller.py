from typing import List
import subprocess
import sys
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.layout import Layout


def pyinstaller(scriptname: str, options: List[str]):
	"""
	Build a PyInstaller application for Pyloid.

	Parameters
	----------
	scriptname : str
	    The name of the script to build.
	options : List[str]
	    The options to pass to PyInstaller. (https://pyinstaller.org/en/stable/usage.html#options)
	"""

	console = Console()

	# Get terminal size
	terminal_height = console.size.height
	terminal_width = console.size.width

	# Dynamically calculate left info panel width (50% of total width, minimum 40)
	info_panel_width = max(40, int(terminal_width * 0.5))

	# Format options for display (multiple lines)
	def format_options(options_list):
		if not options_list:
			return 'None'

		# Display each option on separate lines, wrap if too long
		formatted_lines = []
		current_line = ''
		max_line_length = max(30, info_panel_width - 10)  # Consider panel width

		for option in options_list:
			if len(current_line) + len(option) + 1 <= max_line_length:
				current_line += (' ' + option) if current_line else option
			else:
				if current_line:
					formatted_lines.append(current_line)
				current_line = option

		if current_line:
			formatted_lines.append(current_line)

		return '\n'.join(formatted_lines)

	# Info panel content
	formatted_options = format_options(options)
	options_lines = len(formatted_options.split('\n'))
	info_content_lines = 1 + options_lines  # Script(1 line) + Options(multiple lines)
	info_panel_height = info_content_lines + 4  # Content + border + title

	# Dynamically calculate log box height (80% of terminal height, minimum 10 lines)
	available_height = max(10, int(terminal_height * 0.8))
	log_box_height = available_height

	# Calculate maximum log lines (box height - border)
	max_log_lines = log_box_height - 4

	# Create fixed top info panel
	info_panel = Panel(
		f'[bold cyan]Script:[/bold cyan] {scriptname}\n'
		f'[bold cyan]Options:[/bold cyan]\n{formatted_options}',
		title='[bold blue]PyInstaller Build Info[/bold blue]',
		border_style='blue',
		width=info_panel_width,
		height=info_panel_height,
	)

	# Text object for logs
	log_text = Text('', style='dim white')
	log_panel = Panel.fit(
		log_text,
		title='[bold green]Build Log[/bold green]',
		border_style='green',
		height=log_box_height,
	)

	# Create layout
	layout = Layout()
	layout.split_row(
		Layout(info_panel, name='info', size=info_panel_width),  # Left: dynamic width info
		Layout(log_panel, name='log'),  # Right: log box
	)

	def update_log(new_line: str):
		"""Update log text"""
		current_text = str(log_text.plain)
		log_text.plain = current_text + new_line + '\n'
		# Keep only maximum number of lines for latest logs
		lines = log_text.plain.split('\n')
		if len(lines) > max_log_lines:
			log_text.plain = '\n'.join(lines[-max_log_lines:])

	try:
		console.print('[bold blue]🚀 Starting PyInstaller build...[/bold blue]\n')

		# Prepare PyInstaller command
		cmd = [sys.executable, '-m', 'PyInstaller', scriptname] + options

		# Start Live display
		with Live(layout, console=console, refresh_per_second=4) as live:
			# Run PyInstaller with subprocess
			process = subprocess.Popen(
				cmd,
				stdout=subprocess.PIPE,
				stderr=subprocess.STDOUT,
				text=True,
				bufsize=1,
				universal_newlines=True,
			)

			# Capture output in real-time
			while True:
				output = process.stdout.readline()
				if output == '' and process.poll() is not None:
					break
				if output:
					update_log(output.strip())
					live.update(layout)  # Update layout

			# Wait for process completion
			return_code = process.wait()

			if return_code == 0:
				# Success message
				update_log('✓ Build completed successfully!')
				log_panel.border_style = 'green'
				log_panel.title = '[bold green]✓ Build Complete[/bold green]'
				live.update(layout)

				console.print('\n[bold green]🎉 Your application has been built![/bold green]')
				console.print("[dim]Check the 'dist' folder for the executable.[/dim]")
			else:
				# Failure message
				update_log(f'✗ Build failed with return code: {return_code}')
				log_panel.border_style = 'red'
				log_panel.title = '[bold red]✗ Build Failed[/bold red]'
				live.update(layout)

				console.print(
					f'\n[bold red]❌ Build failed with return code: {return_code}[/bold red]'
				)
				raise Exception(f'PyInstaller build failed with return code: {return_code}')

	except FileNotFoundError:
		console.print(
			'\n[bold red]❌ Error: PyInstaller not found. Please install PyInstaller.[/bold red]'
		)
		raise
	except Exception as e:
		console.print(f'\n[bold red]❌ Error occurred during build: {str(e)}[/bold red]')
		raise
