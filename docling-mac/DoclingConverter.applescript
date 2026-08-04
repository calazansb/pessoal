-- Docling Converter
-- App "droplet": arraste PDF, DOCX, PPTX, XLSX, HTML ou imagens para
-- converter em Markdown (o .md aparece ao lado do arquivo original).
-- Clique duplo abre um seletor de arquivos.

on open droppedItems
	my convertItems(droppedItems)
end open

on run
	set chosen to choose file with prompt ¬
		"Escolha os documentos para converter em Markdown:" ¬
		with multiple selections allowed
	my convertItems(chosen)
end run

on convertItems(theItems)
	set wrapperPath to (POSIX path of (path to home folder)) & ".local/bin/docling-convert"
	set cmd to quoted form of wrapperPath & " --notify"
	repeat with f in theItems
		set cmd to cmd & " " & quoted form of (POSIX path of (f as alias))
	end repeat
	try
		-- conversões grandes (ou o download de modelos no 1º uso) demoram
		with timeout of 7200 seconds
			do shell script cmd
		end timeout
	on error errMsg
		display dialog "Erro ao converter:" & return & return & errMsg ¬
			buttons {"OK"} default button "OK" with icon stop
	end try
end convertItems
