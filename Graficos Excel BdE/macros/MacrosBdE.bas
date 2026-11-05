Attribute VB_Name = "MacrosBdE"
' Macros personales BdE (PERSONAL.XLSB de Windows) adaptadas a Excel para Mac.
' Atajos: en Windows CTRL+MAY+letra; en Mac Opcion+Cmd+Mayus+letra.

' Acceso directo: CTRL+MAY+P (Windows) / Opcion+Cmd+Mayus+P (Mac)
' Adaptada a Mac: sin VBScript.RegExp (solo existe en Windows); el cambio Q3 2024 -> 2024 Q3 se hace a mano.

Sub PlanosIngles()
Attribute PlanosIngles.VB_ProcData.VB_Invoke_Func = "P\n14"
    Dim wb As Workbook
    Dim ws As Worksheet
    Dim celda As Range
    Dim textoBuscar As String
    Dim textoReemplazar As String
    Dim solicitudRealizada As Boolean

    solicitudRealizada = False

    For Each wb In Workbooks
        Set ws = Nothing
        On Error Resume Next
        Set ws = wb.Sheets("D1")
        On Error GoTo 0

        If Not ws Is Nothing Then
            textoBuscar = ws.Range("A1").Value

            If Not solicitudRealizada Then
                textoReemplazar = InputBox("Introduce el t" & ChrW(237) & "tulo del informe en ingl" & ChrW(233) & "s (celda A1):" & vbCrLf & "Puedes poner dos l" & ChrW(237) & "neas de texto. Para que se ejecute el salto de l" & ChrW(237) & "nea debes escribir el s" & ChrW(237) & "mbolo barra (/)")
                If Trim(textoReemplazar) = "" Then
                    MsgBox "El texto de reemplazo no puede estar vac" & ChrW(237) & "o."
                    Exit Sub
                End If
                Dim partes() As String
                partes = Split(textoReemplazar, "/")
                If UBound(partes) > 0 Then
                    textoReemplazar = partes(0) & " " & vbCrLf & partes(1)
                End If
                solicitudRealizada = True
            End If

            ws.Range("A1").Value = textoReemplazar

            For Each celda In ws.UsedRange
                If Not IsError(celda.Value) Then
                    If VarType(celda.Value) = vbString Or VarType(celda.Value) = vbVariant Then
                        Dim contenido As String
                        contenido = Trim(CStr(celda.Value))

                        If InStr(1, contenido, textoBuscar, vbTextCompare) > 0 Then
                            celda.Value = Replace(contenido, textoBuscar, textoReemplazar)
                        End If

                        contenido = Replace(contenido, "Gr" & ChrW(225) & "fico", "Chart")

                        ' Trimestres
                        contenido = Replace(contenido, "IV TR", "Q4")
                        contenido = Replace(contenido, "III TR", "Q3")
                        contenido = Replace(contenido, "II TR", "Q2")
                        contenido = Replace(contenido, "I TR", "Q1")

                        ' Paises
                        contenido = Replace(contenido, "M" & ChrW(233) & "xico", "Mexico")
                        contenido = Replace(contenido, "Per" & ChrW(250), "Peru")
                        contenido = Replace(contenido, "Brasil", "Brazil")
                        contenido = Replace(contenido, "Espa" & ChrW(241) & "a", "Spain")
                        contenido = Replace(contenido, "Estados Unidos", "United States")
                        contenido = Replace(contenido, "Reino Unido", "United kingdom")
                        contenido = Replace(contenido, "Turk" & ChrW(237) & "a", "T" & ChrW(252) & "rkiye")

                        ' Areas
                        contenido = Replace(contenido, "Resto del " & ChrW(225) & "rea del euro", "Rest of the euro area")
                        contenido = Replace(contenido, "Resto de Am" & ChrW(233) & "rica Latina", "Rest of Latin America")
                        contenido = Replace(contenido, "Resto del mundo", "Rest of the world")
                        contenido = Replace(contenido, "Am" & ChrW(233) & "rica Latina", "Rest of the world")

                        ' otros
                        contenido = Replace(contenido, "Fuente", "Source")

                        ' Unidades
                        contenido = Replace(contenido, "Unidades escala izda.:", "Units left-hand scale:")
                        contenido = Replace(contenido, "Unidades escala dcha.:", "Units right-hand scale:")
                        contenido = Replace(contenido, "% del PIB", "% of GDP")

                        ' Q3 2024 -> 2024 Q3 (antes con VBScript.RegExp, que no existe en Mac)
                        celda.Value = TrimestreDetras(contenido)
                    End If

                    If IsDate(celda.Value) Then
                        celda.NumberFormat = "[$-en-GB]dd-mmm-yyyy;@"
                    ElseIf celda.NumberFormat = "[$-es-ES]d-mmm-aaaa;@" Then
                        celda.NumberFormat = "[$-en-GB]dd-mmm-yyyy;@"
                    End If
                End If
            Next celda

        End If
    Next wb

    MsgBox "Sustituci" & ChrW(243) & "n completada en todos los libros abiertos con hoja 'D1'."

End Sub

' Cada Qn aaaa (n de 1 a 4, mayuscula o minuscula, con o sin espacios entre medias) pasa a aaaa Qn
Private Function TrimestreDetras(ByVal texto As String) As String
    Dim i As Long, j As Long, k As Long, n As Long
    Dim salida As String
    i = 1
    n = Len(texto)
    Do While i <= n
        If (Mid(texto, i, 1) = "Q" Or Mid(texto, i, 1) = "q") And i + 1 <= n Then
            If InStr("1234", Mid(texto, i + 1, 1)) > 0 Then
                j = i + 2
                Do While j <= n
                    If Mid(texto, j, 1) <> " " And Mid(texto, j, 1) <> vbTab And Mid(texto, j, 1) <> Chr(160) Then Exit Do
                    j = j + 1
                Loop
                If j + 3 <= n Then
                    Dim anio As String
                    anio = Mid(texto, j, 4)
                    Dim todosDigitos As Boolean
                    todosDigitos = True
                    For k = 1 To 4
                        If Not (Mid(anio, k, 1) Like "#") Then todosDigitos = False
                    Next k
                    If todosDigitos Then
                        salida = salida & anio & " " & Mid(texto, i, 2)
                        i = j + 4
                        GoTo Siguiente
                    End If
                End If
            End If
        End If
        salida = salida & Mid(texto, i, 1)
        i = i + 1
Siguiente:
    Loop
    TrimestreDetras = salida
End Function

Sub FranjasHorizontalesOscuras()
Attribute FranjasHorizontalesOscuras.VB_ProcData.VB_Invoke_Func = "Q\n14"
'
' FranjasHorizontalesOscuras Macro
'
' Acceso directo: CTRL+MAY+q
'
    With Selection.Format.Fill
        .Visible = msoTrue
        .Patterned msoPatternDarkHorizontal
    End With
    With Selection.Format.Fill
        .Visible = msoTrue
        .Patterned msoPatternDarkHorizontal
    End With
    With Selection.Format.Fill
        .Visible = msoTrue
        .ForeColor.RGB = RGB(0, 0, 0)
        .ForeColor.TintAndShade = 0
        .ForeColor.Brightness = 0
        .BackColor.RGB = RGB(128, 128, 128)
        .BackColor.TintAndShade = 0
        .BackColor.Brightness = 0
        .Patterned msoPatternDarkHorizontal
        
    
' Usa una de las dos opciones segun tu objeto:
    On Error Resume Next ' por si el tipo de seleccion no tiene linea
    Selection.ShapeRange.Line.Visible = msoFalse
    Selection.Format.Line.Visible = msoFalse
       On Error GoTo 0

        .BackColor.TintAndShade = 0
        .BackColor.Brightness = 0
    
      End With
    ' --- Quitar borde segun el tipo de seleccion ---
    On Error Resume Next

    Select Case TypeName(Selection)
        Case "Point"
            ' Un solo punto/barra de la serie
            Selection.Format.Line.Visible = msoFalse

        Case "Series"
            ' Serie completa: quitar en la serie y en cada punto
            Dim s As Series, p As Point
            Set s = Selection
            s.Format.Line.Visible = msoFalse
            For Each p In s.Points
                p.Format.Line.Visible = msoFalse
            Next p

        Case "ChartObject"
            ' Si estas en el objeto grafico (forma), quita borde del area del grafico
            Selection.Chart.ChartArea.Format.Line.Visible = msoFalse

        Case "ChartArea", "PlotArea"
            Selection.Format.Line.Visible = msoFalse

        Case Else
            ' Intento generico por si el objeto expone .Format.Line
            Selection.Format.Line.Visible = msoFalse
    End Select

    On Error GoTo 0
End Sub
Sub Punteado90()
Attribute Punteado90.VB_ProcData.VB_Invoke_Func = "W\n14"
'
' Punteado90 Macro
'
' Acceso directo: CTRL+MAY+w
'
    With Selection.Format.Fill
        .Visible = msoTrue
        .Patterned msoPattern90Percent
    End With
    With Selection.Format.Fill
        .Visible = msoTrue
        .Patterned msoPattern90Percent
    End With
    With Selection.Format.Fill
        .Visible = msoTrue
        .ForeColor.RGB = RGB(125, 183, 73)
        .ForeColor.TintAndShade = 0
        .ForeColor.Brightness = 0
        .BackColor.RGB = RGB(255, 255, 255)
        .Patterned msoPattern90Percent
        
    End With

    ' --- Quitar borde segun el tipo de seleccion ---
    On Error Resume Next

    Select Case TypeName(Selection)
        Case "Point"
            ' Un solo punto/barra de la serie
            Selection.Format.Line.Visible = msoFalse

        Case "Series"
            ' Serie completa: quitar en la serie y en cada punto
            Dim s As Series, p As Point
            Set s = Selection
            s.Format.Line.Visible = msoFalse
            For Each p In s.Points
                p.Format.Line.Visible = msoFalse
            Next p

        Case "ChartObject"
            ' Si estas en el objeto grafico (forma), quita borde del area del grafico
            Selection.Chart.ChartArea.Format.Line.Visible = msoFalse

        Case "ChartArea", "PlotArea"
            Selection.Format.Line.Visible = msoFalse

        Case Else
            ' Intento generico por si el objeto expone .Format.Line
            Selection.Format.Line.Visible = msoFalse
    End Select

    On Error GoTo 0
End Sub

Sub FranjasDiagonales()
Attribute FranjasDiagonales.VB_ProcData.VB_Invoke_Func = "E\n14"
'
' FranjasDiagonales Macro
'
' Acceso directo: CTRL+MAY+e
'
    With Selection.Format.Fill
        .Visible = msoTrue
        .Patterned msoPatternDarkUpwardDiagonal
    End With
    With Selection.Format.Fill
        .Visible = msoTrue
        .Patterned msoPatternDarkUpwardDiagonal
    End With
    With Selection.Format.Fill
        .Visible = msoTrue
        .ForeColor.RGB = RGB(255, 219, 147)
        .ForeColor.TintAndShade = 0
        .ForeColor.Brightness = 0
        .BackColor.RGB = RGB(255, 240, 210)
        .BackColor.TintAndShade = 0
        .BackColor.Brightness = 0
        .Patterned msoPatternDarkUpwardDiagonal
        
    ' Usa una de las dos opciones segun tu objeto:
    On Error Resume Next ' por si el tipo de seleccion no tiene linea
    Selection.ShapeRange.Line.Visible = msoFalse
    Selection.Format.Line.Visible = msoFalse
       On Error GoTo 0

        .BackColor.TintAndShade = 0
        .BackColor.Brightness = 0
    
      End With
      
    ' --- Quitar borde segun el tipo de seleccion ---
    On Error Resume Next

    Select Case TypeName(Selection)
        Case "Point"
            ' Un solo punto/barra de la serie
            Selection.Format.Line.Visible = msoFalse

        Case "Series"
            ' Serie completa: quitar en la serie y en cada punto
            Dim s As Series, p As Point
            Set s = Selection
            s.Format.Line.Visible = msoFalse
            For Each p In s.Points
                p.Format.Line.Visible = msoFalse
            Next p

        Case "ChartObject"
            ' Si estas en el objeto grafico (forma), quita borde del area del grafico
            Selection.Chart.ChartArea.Format.Line.Visible = msoFalse

        Case "ChartArea", "PlotArea"
            Selection.Format.Line.Visible = msoFalse

        Case Else
            ' Intento generico por si el objeto expone .Format.Line
            Selection.Format.Line.Visible = msoFalse
    End Select

    On Error GoTo 0

    
End Sub
Sub ZigZag()
Attribute ZigZag.VB_ProcData.VB_Invoke_Func = "R\n14"
'
' ZigZag Macro
'
' Acceso directo: CTRL+MAY+r
'
    With Selection.Format.Fill
        .Visible = msoTrue
        .Patterned msoPatternZigZag
    End With
    With Selection.Format.Fill
        .Visible = msoTrue
        .Patterned msoPatternZigZag
    End With
    With Selection.Format.Fill
        .Visible = msoTrue
        .ForeColor.RGB = RGB(239, 144, 17)
        .ForeColor.TintAndShade = 0
        .ForeColor.Brightness = 0
        .BackColor.RGB = RGB(255, 192, 0)
        .BackColor.TintAndShade = 0
        .BackColor.Brightness = 0
        .Patterned msoPatternZigZag
        
    ' Usa una de las dos opciones segun tu objeto:
    On Error Resume Next ' por si el tipo de seleccion no tiene linea
    Selection.ShapeRange.Line.Visible = msoFalse
    Selection.Format.Line.Visible = msoFalse
       On Error GoTo 0

        .BackColor.TintAndShade = 0
        .BackColor.Brightness = 0
    
   End With
   
       ' --- Quitar borde segun el tipo de seleccion ---
    On Error Resume Next

    Select Case TypeName(Selection)
        Case "Point"
            ' Un solo punto/barra de la serie
            Selection.Format.Line.Visible = msoFalse

        Case "Series"
            ' Serie completa: quitar en la serie y en cada punto
            Dim s As Series, p As Point
            Set s = Selection
            s.Format.Line.Visible = msoFalse
            For Each p In s.Points
                p.Format.Line.Visible = msoFalse
            Next p

        Case "ChartObject"
            ' Si estas en el objeto grafico (forma), quita borde del area del grafico
            Selection.Chart.ChartArea.Format.Line.Visible = msoFalse

        Case "ChartArea", "PlotArea"
            Selection.Format.Line.Visible = msoFalse

        Case Else
            ' Intento generico por si el objeto expone .Format.Line
            Selection.Format.Line.Visible = msoFalse
    End Select

    On Error GoTo 0
End Sub
Sub FranjasVerticalesEstrechas()
Attribute FranjasVerticalesEstrechas.VB_ProcData.VB_Invoke_Func = "T\n14"
'
' FranjasVerticalesEstrechas Macro
'
' Acceso directo: CTRL+MAY+t
'
    With Selection.Format.Fill
        .Visible = msoTrue
        .Patterned msoPatternNarrowVertical
    End With
    With Selection.Format.Fill
        .Visible = msoTrue
        .Patterned msoPatternNarrowVertical
    End With
    With Selection.Format.Fill
        .Visible = msoTrue
        .ForeColor.RGB = RGB(29, 81, 145)
        .ForeColor.TintAndShade = 0
        .ForeColor.Brightness = 0
        .BackColor.RGB = RGB(174, 206, 244)
        .BackColor.TintAndShade = 0
        .BackColor.Brightness = 0
        .Patterned msoPatternNarrowVertical
    End With
       ' --- Quitar borde segun el tipo de seleccion ---
    On Error Resume Next

    Select Case TypeName(Selection)
        Case "Point"
            ' Un solo punto/barra de la serie
            Selection.Format.Line.Visible = msoFalse

        Case "Series"
            ' Serie completa: quitar en la serie y en cada punto
            Dim s As Series, p As Point
            Set s = Selection
            s.Format.Line.Visible = msoFalse
            For Each p In s.Points
                p.Format.Line.Visible = msoFalse
            Next p

        Case "ChartObject"
            ' Si estas en el objeto grafico (forma), quita borde del area del grafico
            Selection.Chart.ChartArea.Format.Line.Visible = msoFalse

        Case "ChartArea", "PlotArea"
            Selection.Format.Line.Visible = msoFalse

        Case Else
            ' Intento generico por si el objeto expone .Format.Line
            Selection.Format.Line.Visible = msoFalse
    End Select

    On Error GoTo 0
End Sub
Sub FranjasDiagonalesAnchas()
Attribute FranjasDiagonalesAnchas.VB_ProcData.VB_Invoke_Func = "Y\n14"
'
' FranjasDiagonalesAnchas Macro
'
' Acceso directo: CTRL+MAY+y
'
    With Selection.Format.Fill
        .Visible = msoTrue
        .Patterned msoPatternWideDownwardDiagonal
    End With
    With Selection.Format.Fill
        .Visible = msoTrue
        .Patterned msoPatternWideDownwardDiagonal
    End With
    With Selection.Format.Fill
        .Visible = msoTrue
        .ForeColor.RGB = RGB(195, 15, 186)
        .ForeColor.TintAndShade = 0
        .ForeColor.Brightness = 0
        .BackColor.RGB = RGB(242, 87, 235)
        .BackColor.TintAndShade = 0
        .BackColor.Brightness = 0
        .Patterned msoPatternWideDownwardDiagonal
        
    ' Usa una de las dos opciones segun tu objeto:
    On Error Resume Next ' por si el tipo de seleccion no tiene linea
    Selection.ShapeRange.Line.Visible = msoFalse
    Selection.Format.Line.Visible = msoFalse
       On Error GoTo 0

        .BackColor.TintAndShade = 0
        .BackColor.Brightness = 0
    
    End With
    
        ' --- Quitar borde segun el tipo de seleccion ---
    On Error Resume Next

    Select Case TypeName(Selection)
        Case "Point"
            ' Un solo punto/barra de la serie
            Selection.Format.Line.Visible = msoFalse

        Case "Series"
            ' Serie completa: quitar en la serie y en cada punto
            Dim s As Series, p As Point
            Set s = Selection
            s.Format.Line.Visible = msoFalse
            For Each p In s.Points
                p.Format.Line.Visible = msoFalse
            Next p

        Case "ChartObject"
            ' Si estas en el objeto grafico (forma), quita borde del area del grafico
            Selection.Chart.ChartArea.Format.Line.Visible = msoFalse

        Case "ChartArea", "PlotArea"
            Selection.Format.Line.Visible = msoFalse

        Case Else
            ' Intento generico por si el objeto expone .Format.Line
            Selection.Format.Line.Visible = msoFalse
    End Select

    On Error GoTo 0
End Sub

Sub FranjasVerticalesOsc()
Attribute FranjasVerticalesOsc.VB_ProcData.VB_Invoke_Func = "U\n14"
'
' FranjasVerticalesOsc Macro
'
' Acceso directo: CTRL+MAY+u
'
    With Selection.Format.Fill
        .Visible = msoTrue
        .Patterned msoPatternDarkVertical
    End With
    With Selection.Format.Fill
        .Visible = msoTrue
        .Patterned msoPatternDarkVertical
    End With
    With Selection.Format.Fill
        .Visible = msoTrue
        .ForeColor.RGB = RGB(127, 60, 47)
        .ForeColor.TintAndShade = 0
        .ForeColor.Brightness = 0
        .BackColor.RGB = RGB(201, 121, 107)
        .BackColor.TintAndShade = 0
        .BackColor.Brightness = 0
        .Patterned msoPatternDarkVertical
        
    ' Usa una de las dos opciones segun tu objeto:
    On Error Resume Next ' por si el tipo de seleccion no tiene linea
    Selection.ShapeRange.Line.Visible = msoFalse
    Selection.Format.Line.Visible = msoFalse
       On Error GoTo 0

        .BackColor.TintAndShade = 0
        .BackColor.Brightness = 0
    
    End With
    
    ' --- Quitar borde segun el tipo de seleccion ---
    On Error Resume Next

    Select Case TypeName(Selection)
        Case "Point"
            ' Un solo punto/barra de la serie
            Selection.Format.Line.Visible = msoFalse

        Case "Series"
            ' Serie completa: quitar en la serie y en cada punto
            Dim s As Series, p As Point
            Set s = Selection
            s.Format.Line.Visible = msoFalse
            For Each p In s.Points
                p.Format.Line.Visible = msoFalse
            Next p

        Case "ChartObject"
            ' Si estas en el objeto grafico (forma), quita borde del area del grafico
            Selection.Chart.ChartArea.Format.Line.Visible = msoFalse

        Case "ChartArea", "PlotArea"
            Selection.Format.Line.Visible = msoFalse

        Case Else
            ' Intento generico por si el objeto expone .Format.Line
            Selection.Format.Line.Visible = msoFalse
    End Select

    On Error GoTo 0
End Sub
Sub LineaNegra()
Attribute LineaNegra.VB_ProcData.VB_Invoke_Func = "A\n14"
'
' LineaNegra Macro
'
' Acceso directo: CTRL+MAY+a

    CargarTemaBdE
'
    With Selection.Format.Line
        .Visible = msoTrue
        .Weight = 2.25
    End With
    With Selection.Format.Line
        .Visible = msoTrue
        .DashStyle = msoLineSolid
        .ForeColor.RGB = RGB(0, 0, 0)
        .ForeColor.TintAndShade = 0
        .ForeColor.Brightness = 0
        .Transparency = 0
        
    End With
    
  If TypeName(Selection) = "Series" Then
        Selection.MarkerStyle = xlMarkerStyleNone
    Else
        MsgBox "Selecciona una serie del gr" & ChrW(225) & "fico primero.", vbExclamation
    End If


    
End Sub
Sub LineaVerde()
Attribute LineaVerde.VB_ProcData.VB_Invoke_Func = "S\n14"
'
' Verde Macro
'
' Acceso directo: CTRL+MAY+s
'
    CargarTemaBdE
    With Selection.Format.Line
        .Visible = msoTrue
        .Weight = 2.25
    End With
    
      If TypeName(Selection) = "Series" Then
        Selection.MarkerStyle = xlMarkerStyleNone
    Else
        MsgBox "Selecciona una serie del gr" & ChrW(225) & "fico primero.", vbExclamation
    End If
    
    With Selection.Format.Line
        .Visible = msoTrue
        .DashStyle = msoLineSysDash
    End With
    With Selection.Format.Line
        .Visible = msoTrue
        .ForeColor.RGB = RGB(125, 183, 73)
        .ForeColor.TintAndShade = 0
        .ForeColor.Brightness = 0
        .Transparency = 0
    End With
    Selection.MarkerStyle = -4142
End Sub
Sub NaranjaPuntoRedondo()
Attribute NaranjaPuntoRedondo.VB_ProcData.VB_Invoke_Func = "D\n14"
'
' NaranjaPuntoRedondo Macro
'
' Acceso directo: CTRL+MAY+d
'
    CargarTemaBdE
    With Selection.Format.Line
        .Visible = msoTrue
        .ForeColor.RGB = RGB(255, 219, 147)
        .ForeColor.TintAndShade = 0
        .ForeColor.Brightness = 0
        .Transparency = 0
    End With
    
      If TypeName(Selection) = "Series" Then
        Selection.MarkerStyle = xlMarkerStyleNone
    Else
        MsgBox "Selecciona una serie del gr" & ChrW(225) & "fico primero.", vbExclamation
    End If
    
    With Selection.Format.Line
        .Visible = msoTrue
        .Weight = 2.25
    End With
    With Selection.Format.Line
        .Visible = msoTrue
        .DashStyle = msoLineSysDot
    End With
    Selection.MarkerStyle = -4142
End Sub

Sub Triangulo()
Attribute Triangulo.VB_ProcData.VB_Invoke_Func = "F\n14"
'
' Triangulo Macro
' Acceso directo: CTRL+MAY+f
'
        CargarTemaBdE
Dim ser As Series
    
    ' Intentar tomar la serie actualmente seleccionada
    On Error Resume Next
    Set ser = Selection
    On Error GoTo 0
    
    If ser Is Nothing Then
        MsgBox "Selecciona una serie de gr" & ChrW(225) & "fico antes de ejecutar la macro.", vbExclamation
 Exit Sub
    End If

    ' --- Formato de la linea de la serie (visible, color de tema y grosor)
    With ser.Format.Line
        .Visible = msoTrue
        .DashStyle = msoLineSolid
        .ForeColor.RGB = RGB(239, 144, 17)                            ' Color de linea
        .Weight = 2.25
        .Transparency = 0
    End With

    ' --- Marcadores: estilo cuadrado y tamano 6
    ser.MarkerStyle = xlMarkerStyleTriangle
    ser.MarkerSize = 6

    ' --- Quitar el borde del marcador y establecer relleno
    ' Usar propiedades 'clasicas' para no afectar la linea de la serie
    On Error Resume Next
    ser.MarkerForegroundColorIndex = xlColorIndexNone              ' Sin borde
    ser.MarkerBackgroundColor = RGB(239, 144, 17)                 ' Relleno
    On Error GoTo 0

    ' --- (Plan B) Si tu version no respeta las propiedades anteriores para todos los puntos,
    ' iterar por los puntos y aplicar el mismo ajuste de color-indice:
    Dim p As Point
    For Each p In ser.Points
        On Error Resume Next
        p.MarkerForegroundColorIndex = xlColorIndexNone            ' Sin borde del marcador
        p.MarkerBackgroundColor = RGB(239, 144, 17)               ' Relleno del marcador
        On Error GoTo 0
    Next p

    ' Seguridad: asegurate de que la linea de la serie se mantenga visible (por si algun tema la oculta)
    ser.Format.Line.Visible = msoTrue
End Sub

Sub Cuadrado()
Attribute Cuadrado.VB_ProcData.VB_Invoke_Func = "G\n14"

' Acceso directo: CTRL+MAY+g
         
    CargarTemaBdE

    Dim ser As Series
    
    ' Intentar tomar la serie actualmente seleccionada
    On Error Resume Next
    Set ser = Selection
    On Error GoTo 0
    
    If ser Is Nothing Then
        MsgBox "Selecciona una serie de gr" & ChrW(225) & "fico antes de ejecutar la macro.", vbExclamation
 Exit Sub
    End If

    ' --- Formato de la linea de la serie (visible, color de tema y grosor)
    With ser.Format.Line
        .Visible = msoTrue
        .DashStyle = msoLineSolid
        .ForeColor.RGB = RGB(174, 206, 244)                         ' Color de linea
        .Weight = 2.25
        .Transparency = 0
    End With

    ' --- Marcadores: estilo cuadrado y tamano 5
    ser.MarkerStyle = xlMarkerStyleSquare
    ser.MarkerSize = 5

    ' --- Quitar el borde del marcador y establecer relleno
    ' Usar propiedades 'clasicas' para no afectar la linea de la serie
    On Error Resume Next
    ser.MarkerForegroundColorIndex = xlColorIndexNone              ' Sin borde
    ser.MarkerBackgroundColor = RGB(174, 206, 244)                 ' Relleno
    On Error GoTo 0

    ' --- (Plan B) Si tu version no respeta las propiedades anteriores para todos los puntos,
    ' iterar por los puntos y aplicar el mismo ajuste de color-indice:
    Dim p As Point
    For Each p In ser.Points
        On Error Resume Next
        p.MarkerForegroundColorIndex = xlColorIndexNone            ' Sin borde del marcador
        p.MarkerBackgroundColor = RGB(174, 206, 244)               ' Relleno del marcador
        On Error GoTo 0
    Next p

    ' Seguridad: asegurate de que la linea de la serie se mantenga visible (por si algun tema la oculta)
    ser.Format.Line.Visible = msoTrue
End Sub
Sub Circulo()
Attribute Circulo.VB_ProcData.VB_Invoke_Func = "H\n14"

' Acceso directo: CTRL+MAY+h
    CargarTemaBdE
    Dim ser As Series
    
    ' Intentar tomar la serie actualmente seleccionada
    On Error Resume Next
    Set ser = Selection
    On Error GoTo 0
    
    If ser Is Nothing Then
        MsgBox "Selecciona una serie de gr" & ChrW(225) & "fico antes de ejecutar la macro.", vbExclamation
 Exit Sub
    End If

    ' --- Formato de la linea de la serie (visible, color de tema y grosor)
    With ser.Format.Line
        .Visible = msoTrue
        .DashStyle = msoLineSolid
        .ForeColor.RGB = RGB(195, 15, 186)                         ' Color de linea
        .Weight = 2.25
        .Transparency = 0
    End With

    ' --- Marcadores: estilo cuadrado y tamano 5
    ser.MarkerStyle = xlMarkerStyleCircle
    ser.MarkerSize = 5

    ' --- Quitar el borde del marcador y establecer relleno
    ' Usar propiedades 'clasicas' para no afectar la linea de la serie
    On Error Resume Next
    ser.MarkerForegroundColorIndex = xlColorIndexNone             ' Sin borde
    ser.MarkerBackgroundColor = RGB(195, 15, 186)                 ' Relleno
    On Error GoTo 0

    ' --- (Plan B) Si tu version no respeta las propiedades anteriores para todos los puntos,
    ' iterar por los puntos y aplicar el mismo ajuste de color-indice:
    Dim p As Point
    For Each p In ser.Points
        On Error Resume Next
        p.MarkerForegroundColorIndex = xlColorIndexNone          ' Sin borde del marcador
        p.MarkerBackgroundColor = RGB(195, 15, 186)              ' Relleno del marcador
        On Error GoTo 0
    Next p

    ' Seguridad: asegurate de que la linea de la serie se mantenga visible (por si algun tema la oculta)
    ser.Format.Line.Visible = msoTrue
End Sub
Sub Diamante()
Attribute Diamante.VB_ProcData.VB_Invoke_Func = "J\n14"

' Acceso directo: CTRL+MAY+j
        
    CargarTemaBdE
    Dim ser As Series
    
    ' Intentar tomar la serie actualmente seleccionada
    On Error Resume Next
    Set ser = Selection
    On Error GoTo 0
    
    If ser Is Nothing Then
        MsgBox "Selecciona una serie de gr" & ChrW(225) & "fico antes de ejecutar la macro.", vbExclamation
 Exit Sub
    End If

    ' --- Formato de la linea de la serie (visible, color de tema y grosor)
    With ser.Format.Line
        .Visible = msoTrue
        .DashStyle = msoLineSolid
        .ForeColor.RGB = RGB(201, 121, 107)                         ' Color de linea
        .Weight = 2.25
        .Transparency = 0
    End With

    ' --- Marcadores: estilo cuadrado y tamano 6
    ser.MarkerStyle = xlMarkerStyleDiamond
    ser.MarkerSize = 6

    ' --- Quitar el borde del marcador y establecer relleno
    ' Usar propiedades 'clasicas' para no afectar la linea de la serie
    On Error Resume Next
    ser.MarkerForegroundColorIndex = xlColorIndexNone              ' Sin borde
    ser.MarkerBackgroundColor = RGB(201, 121, 107)                 ' Relleno
    On Error GoTo 0

    ' --- (Plan B) Si tu version no respeta las propiedades anteriores para todos los puntos,
    ' iterar por los puntos y aplicar el mismo ajuste de color-indice:
    Dim p As Point
    For Each p In ser.Points
        On Error Resume Next
        p.MarkerForegroundColorIndex = xlColorIndexNone            ' Sin borde del marcador
        p.MarkerBackgroundColor = RGB(201, 121, 107)              ' Relleno del marcador
        On Error GoTo 0
    Next p

    ' Seguridad: asegurate de que la linea de la serie se mantenga visible (por si algun tema la oculta)
    ser.Format.Line.Visible = msoTrue
End Sub


' Carga los colores BdE_2026. En Mac, de la carpeta de temas de Office (donde los instala Office); en Windows, de
' la unidad de red de siempre. Si no esta, sigue sin parar la macro.
Private Sub CargarTemaBdE()
    Dim ruta As String
#If Mac Then
    ' Application.StartupPath = .../User Content.localized/Startup.localized/Excel
    ruta = Application.StartupPath
    ruta = Left(ruta, InStrRev(ruta, "/Startup") - 1) & "/Themes.localized/Theme Colors/BdE_2026.xml"
#Else
    ruta = "Y:\Becfgusr\Plantillas\Document Themes\Theme Colors\BdE_2026.xml"
#End If
    On Error Resume Next
    ActiveWorkbook.Theme.ThemeColorScheme.Load ruta
    On Error GoTo 0
End Sub


Sub RobotoMedium()
Attribute RobotoMedium.VB_ProcData.VB_Invoke_Func = "M\n14"
'Acceso directo: CTRL+MAY+m

    On Error Resume Next
    With Selection.Font
        .NameComplexScript = "Roboto Medium"
        .NameFarEast = "Roboto Medium"
        .Name = "Roboto Medium"
    End With
End Sub

Sub RobotoLight()
Attribute RobotoLight.VB_ProcData.VB_Invoke_Func = "L\n14"
'Acceso directo: CTRL+MAY+l
    On Error Resume Next
    With Selection.Font
        .NameComplexScript = "Roboto Light"
        .NameFarEast = "Roboto Light"
        .Name = "Roboto Light"
    End With
End Sub

Sub RobotoRegular()
Attribute RobotoRegular.VB_ProcData.VB_Invoke_Func = "N\n14"
'Acceso directo: CTRL+MAY+n
    On Error Resume Next
    With Selection.Font
        .NameComplexScript = "Roboto"
        .NameFarEast = "Roboto"
        .Name = "Roboto"
    End With
End Sub


