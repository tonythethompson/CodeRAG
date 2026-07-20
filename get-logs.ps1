$stream = "2026/07/20/[`$LATEST]cb660985e8fd498c892ebe5eca8590ba"
$result = aws logs get-log-events --log-group-name "/aws/lambda/coderag-QueryFunction-mmwkIGSMW5bz" --log-stream-name $stream --region us-east-1 --output json
$result | Out-File -FilePath "D:\Dev\CodeRAG\qevents.json" -Encoding utf8
