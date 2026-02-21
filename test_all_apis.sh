#!/bin/bash
# ============================================================================
# Test Completo API - Garage Manager (Gestionale Officina)
# ============================================================================
# Testa TUTTE le API con TUTTI i campi e gli edge case principali.
# Uso: bash test_all_apis.sh [BASE_URL]
# Default: http://localhost:8000
# ============================================================================

BASE_URL="${1:-http://localhost:8000}"
API="$BASE_URL/api/v1"
PASS=0
FAIL=0
WARN=0
ERRORS=""

# Colori
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Helpers
check() {
    local name="$1"
    local expected_code="$2"
    local actual_code="$3"
    local body="$4"

    if [ "$actual_code" == "$expected_code" ]; then
        echo -e "  ${GREEN}✓ PASS${NC} $name (HTTP $actual_code)"
        PASS=$((PASS+1))
    else
        echo -e "  ${RED}✗ FAIL${NC} $name — atteso $expected_code, ricevuto $actual_code"
        echo -e "    ${RED}Body: $(echo "$body" | head -c 300)${NC}"
        FAIL=$((FAIL+1))
        ERRORS="$ERRORS\n  ✗ $name (atteso $expected_code, ricevuto $actual_code)"
    fi
}

# Esegue curl e restituisce (http_code, body)
api() {
    local method="$1"
    local url="$2"
    local data="$3"

    if [ -n "$data" ]; then
        RESPONSE=$(curl -s -w "\n%{http_code}" -X "$method" "$url" \
            -H "Content-Type: application/json" \
            -d "$data" 2>/dev/null)
    else
        RESPONSE=$(curl -s -w "\n%{http_code}" -X "$method" "$url" 2>/dev/null)
    fi

    BODY=$(echo "$RESPONSE" | sed '$d')
    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
}

extract_id() {
    echo "$1" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null
}

extract_field() {
    echo "$1" | python3 -c "import sys,json; print(json.load(sys.stdin)['$2'])" 2>/dev/null
}

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║       TEST COMPLETO API - GARAGE MANAGER                    ║${NC}"
echo -e "${BOLD}║       $(date '+%Y-%m-%d %H:%M:%S')                                    ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# 0. HEALTH CHECK
# ============================================================================
echo -e "${CYAN}━━━ 0. HEALTH CHECK ━━━${NC}"
api GET "$BASE_URL/docs"
if [ "$HTTP_CODE" == "200" ]; then
    echo -e "  ${GREEN}✓ Server raggiungibile${NC}"
else
    echo -e "  ${RED}✗ Server non raggiungibile su $BASE_URL${NC}"
    exit 1
fi

# ============================================================================
# 1. CLIENTI
# ============================================================================
echo ""
echo -e "${CYAN}━━━ 1. CLIENTI ━━━${NC}"

# 1.1 Crea cliente persona fisica (tutti i campi)
api POST "$API/clients/" '{
    "name": "Mario",
    "surname": "Rossi",
    "is_company": false,
    "tax_id": "RSSMRA85M01H501Z",
    "address": "Via Roma 1",
    "city": "Roma",
    "zip_code": "00100",
    "province": "RM",
    "phone": "+39 06 1234567",
    "email": "mario.rossi@test.it",
    "notes": "Cliente test persona fisica",
    "country_code": "IT",
    "is_foreign": false,
    "sdi_code": "0000000",
    "pec": "mario.rossi@pec.it",
    "vat_regime": "RF01",
    "vat_exemption": false,
    "split_payment": false,
    "default_vat_rate": 22.00,
    "payment_terms_days": 30,
    "payment_method_default": "bank_transfer",
    "default_discount_percent": 5.0,
    "billing_address": "Via Fattura 10",
    "billing_city": "Milano",
    "billing_zip_code": "20100",
    "billing_province": "MI",
    "credit_limit": 10000.00,
    "credit_limit_action": "warn"
}'
check "Crea cliente persona fisica" "201" "$HTTP_CODE" "$BODY"
CLIENT_PF_ID=$(extract_id "$BODY")
echo "    → CLIENT_PF_ID=$CLIENT_PF_ID"

# 1.2 Crea cliente azienda (tutti i campi)
api POST "$API/clients/" '{
    "name": "Officina Bianchi Srl",
    "is_company": true,
    "tax_id": "00488410010",
    "address": "Via Industria 5",
    "city": "Torino",
    "zip_code": "10100",
    "province": "TO",
    "phone": "+39 011 9876543",
    "email": "info@bianchi-srl.it",
    "notes": "Cliente test azienda",
    "country_code": "IT",
    "is_foreign": false,
    "sdi_code": "M5UXCR1",
    "vat_regime": "RF01",
    "vat_exemption": false,
    "split_payment": false,
    "default_vat_rate": 22.00,
    "payment_terms_days": 60,
    "payment_method_default": "bank_transfer",
    "credit_limit": 50000.00,
    "credit_limit_action": "block"
}'
check "Crea cliente azienda" "201" "$HTTP_CODE" "$BODY"
CLIENT_AZ_ID=$(extract_id "$BODY")
echo "    → CLIENT_AZ_ID=$CLIENT_AZ_ID"

# 1.3 Crea cliente estero
api POST "$API/clients/" '{
    "name": "John",
    "surname": "Smith",
    "is_company": false,
    "tax_id": "GB123456789",
    "address": "10 Downing Street",
    "city": "London",
    "zip_code": "SW1A",
    "province": "LDN",
    "country_code": "GB",
    "is_foreign": true,
    "sdi_code": "XXXXXXX",
    "vat_exemption": true,
    "vat_exemption_code": "N3.1"
}'
check "Crea cliente estero" "201" "$HTTP_CODE" "$BODY"
CLIENT_ESTERO_ID=$(extract_id "$BODY")
echo "    → CLIENT_ESTERO_ID=$CLIENT_ESTERO_ID"

# 1.4 Crea cliente forfettario (RF19)
api POST "$API/clients/" '{
    "name": "Luca",
    "surname": "Verdi",
    "is_company": false,
    "tax_id": "VRDLCU90A01H501X",
    "address": "Via Forfettari 3",
    "city": "Napoli",
    "zip_code": "80100",
    "province": "NA",
    "vat_regime": "RF19",
    "vat_exemption": false
}'
check "Crea cliente forfettario" "201" "$HTTP_CODE" "$BODY"
CLIENT_FORF_ID=$(extract_id "$BODY")
echo "    → CLIENT_FORF_ID=$CLIENT_FORF_ID"

# 1.5 Lista clienti
api GET "$API/clients/?page=1&per_page=10"
check "Lista clienti" "200" "$HTTP_CODE" "$BODY"

# 1.6 Dettaglio cliente
api GET "$API/clients/$CLIENT_PF_ID"
check "Dettaglio cliente PF" "200" "$HTTP_CODE" "$BODY"

# 1.7 Aggiorna cliente
api PUT "$API/clients/$CLIENT_PF_ID" '{
    "phone": "+39 06 9999999",
    "notes": "Nota aggiornata via test"
}'
check "Aggiorna cliente" "200" "$HTTP_CODE" "$BODY"

# 1.8 Edge case: cliente non trovato
api GET "$API/clients/00000000-0000-0000-0000-000000000000"
check "Cliente non trovato → 404" "404" "$HTTP_CODE" "$BODY"

# 1.9 Edge case: nome vuoto
api POST "$API/clients/" '{"name": ""}'
check "Nome vuoto → 422" "422" "$HTTP_CODE" "$BODY"

# ============================================================================
# 2. VEICOLI
# ============================================================================
echo ""
echo -e "${CYAN}━━━ 2. VEICOLI ━━━${NC}"

# 2.1 Crea veicolo (tutti i campi)
api POST "$API/vehicles/" "{
    \"client_id\": \"$CLIENT_PF_ID\",
    \"plate\": \"AB123CD\",
    \"brand\": \"Fiat\",
    \"model\": \"Panda\",
    \"year\": 2020,
    \"vin\": \"WVWZZZ3CZWE123456\",
    \"fuel_type\": \"benzina\",
    \"current_km\": 45000,
    \"color\": \"Rosso\",
    \"notes\": \"Prima auto test\"
}"
check "Crea veicolo" "201" "$HTTP_CODE" "$BODY"
VEHICLE_ID=$(extract_id "$BODY")
echo "    → VEHICLE_ID=$VEHICLE_ID"

# 2.2 Crea secondo veicolo
api POST "$API/vehicles/" "{
    \"client_id\": \"$CLIENT_AZ_ID\",
    \"plate\": \"EF456GH\",
    \"brand\": \"Mercedes\",
    \"model\": \"Sprinter\",
    \"year\": 2022,
    \"fuel_type\": \"diesel\",
    \"current_km\": 120000,
    \"notes\": \"Furgone aziendale\"
}"
check "Crea secondo veicolo" "201" "$HTTP_CODE" "$BODY"
VEHICLE_AZ_ID=$(extract_id "$BODY")
echo "    → VEHICLE_AZ_ID=$VEHICLE_AZ_ID"

# 2.3 Lista veicoli
api GET "$API/vehicles/?page=1&per_page=10"
check "Lista veicoli" "200" "$HTTP_CODE" "$BODY"

# 2.4 Dettaglio veicolo
api GET "$API/vehicles/$VEHICLE_ID"
check "Dettaglio veicolo" "200" "$HTTP_CODE" "$BODY"

# 2.5 Veicoli per cliente
api GET "$API/vehicles/client/$CLIENT_PF_ID"
check "Veicoli per cliente" "200" "$HTTP_CODE" "$BODY"

# 2.6 Aggiorna veicolo
api PUT "$API/vehicles/$VEHICLE_ID" '{"current_km": 46000, "notes": "Aggiornato km"}'
check "Aggiorna veicolo" "200" "$HTTP_CODE" "$BODY"

# 2.7 Edge case: targa duplicata
api POST "$API/vehicles/" "{
    \"client_id\": \"$CLIENT_PF_ID\",
    \"plate\": \"AB123CD\",
    \"brand\": \"Test\",
    \"model\": \"Duplicato\"
}"
check "Targa duplicata → 409" "409" "$HTTP_CODE" "$BODY"

# ============================================================================
# 3. TECNICI
# ============================================================================
echo ""
echo -e "${CYAN}━━━ 3. TECNICI ━━━${NC}"

# 3.1 Crea tecnico (tutti i campi)
api POST "$API/technicians/" '{
    "name": "Giuseppe",
    "surname": "Meccanico",
    "phone": "+39 333 1234567",
    "email": "giuseppe@officina.it",
    "specialization": "Elettrauto",
    "is_active": true,
    "hourly_rate": 35.50
}'
check "Crea tecnico" "201" "$HTTP_CODE" "$BODY"
TECH_ID=$(extract_id "$BODY")
echo "    → TECH_ID=$TECH_ID"

# 3.2 Lista tecnici
api GET "$API/technicians/"
check "Lista tecnici" "200" "$HTTP_CODE" "$BODY"

# 3.3 Dettaglio tecnico
api GET "$API/technicians/$TECH_ID"
check "Dettaglio tecnico" "200" "$HTTP_CODE" "$BODY"

# 3.4 Aggiorna tecnico
api PUT "$API/technicians/$TECH_ID" '{"specialization": "Motorista", "hourly_rate": 40.00}'
check "Aggiorna tecnico" "200" "$HTTP_CODE" "$BODY"

# ============================================================================
# 4. CATEGORIE RICAMBI
# ============================================================================
echo ""
echo -e "${CYAN}━━━ 4. CATEGORIE RICAMBI ━━━${NC}"

# 4.1 Crea categoria padre
api POST "$API/part-categories/" '{
    "name": "Motore",
    "description": "Parti del motore",
    "is_active": true
}'
check "Crea categoria padre" "201" "$HTTP_CODE" "$BODY"
CAT_MOTORE_ID=$(extract_id "$BODY")
echo "    → CAT_MOTORE_ID=$CAT_MOTORE_ID"

# 4.2 Crea sottocategoria
api POST "$API/part-categories/" "{
    \"name\": \"Filtri\",
    \"description\": \"Filtri del motore\",
    \"parent_id\": \"$CAT_MOTORE_ID\",
    \"is_active\": true
}"
check "Crea sottocategoria" "201" "$HTTP_CODE" "$BODY"
CAT_FILTRI_ID=$(extract_id "$BODY")
echo "    → CAT_FILTRI_ID=$CAT_FILTRI_ID"

# 4.3 Lista categorie
api GET "$API/part-categories/"
check "Lista categorie" "200" "$HTTP_CODE" "$BODY"

# ============================================================================
# 5. RICAMBI
# ============================================================================
echo ""
echo -e "${CYAN}━━━ 5. RICAMBI ━━━${NC}"

# 5.1 Crea ricambio (tutti i campi)
api POST "$API/parts/" "{
    \"code\": \"FO-001\",
    \"description\": \"Filtro olio Fiat Panda\",
    \"brand\": \"Bosch\",
    \"compatible_models\": \"Fiat Panda, Fiat 500, Lancia Ypsilon\",
    \"purchase_price\": 8.50,
    \"sale_price\": 15.00,
    \"vat_rate\": 22.00,
    \"min_stock_level\": 5,
    \"location\": \"Scaffale A1\",
    \"is_active\": true,
    \"category_id\": \"$CAT_FILTRI_ID\",
    \"unit_of_measure\": \"pz\"
}"
check "Crea ricambio" "201" "$HTTP_CODE" "$BODY"
PART_ID=$(extract_id "$BODY")
echo "    → PART_ID=$PART_ID"

# 5.2 Crea secondo ricambio (litri)
api POST "$API/parts/" "{
    \"code\": \"OL-001\",
    \"description\": \"Olio motore 5W30 sintetico\",
    \"brand\": \"Castrol\",
    \"purchase_price\": 25.00,
    \"sale_price\": 40.00,
    \"vat_rate\": 22.00,
    \"min_stock_level\": 10,
    \"location\": \"Scaffale B2\",
    \"unit_of_measure\": \"lt\"
}"
check "Crea ricambio (litri)" "201" "$HTTP_CODE" "$BODY"
PART_OIL_ID=$(extract_id "$BODY")
echo "    → PART_OIL_ID=$PART_OIL_ID"

# 5.3 Lista ricambi
api GET "$API/parts/?page=1&per_page=20"
check "Lista ricambi" "200" "$HTTP_CODE" "$BODY"

# 5.4 Dettaglio ricambio
api GET "$API/parts/$PART_ID"
check "Dettaglio ricambio" "200" "$HTTP_CODE" "$BODY"

# 5.5 Ricerca ricambi
api GET "$API/parts/?search=olio"
check "Ricerca ricambi" "200" "$HTTP_CODE" "$BODY"

# 5.6 Aggiorna ricambio
api PUT "$API/parts/$PART_ID" '{"sale_price": 16.50, "location": "Scaffale A2"}'
check "Aggiorna ricambio" "200" "$HTTP_CODE" "$BODY"

# 5.7 Movimento magazzino: carico
api POST "$API/parts/$PART_ID/movements" '{
    "part_id": "'$PART_ID'",
    "movement_type": "in",
    "quantity": 20,
    "reference": "DDT 001/2026",
    "notes": "Carico iniziale"
}'
check "Movimento IN (carico)" "201" "$HTTP_CODE" "$BODY"

# 5.8 Carico secondo ricambio
api POST "$API/parts/$PART_OIL_ID/movements" '{
    "part_id": "'$PART_OIL_ID'",
    "movement_type": "in",
    "quantity": 50,
    "reference": "DDT 002/2026",
    "notes": "Carico olio"
}'
check "Movimento IN olio" "201" "$HTTP_CODE" "$BODY"

# 5.9 Storico movimenti
api GET "$API/parts/$PART_ID/movements"
check "Storico movimenti" "200" "$HTTP_CODE" "$BODY"

# 5.10 Edge case: codice duplicato
api POST "$API/parts/" '{"code": "FO-001", "description": "Duplicato", "purchase_price": 1, "sale_price": 2}'
check "Codice duplicato → 409" "409" "$HTTP_CODE" "$BODY"

# 5.11 Edge case: prezzo vendita < acquisto
api POST "$API/parts/" '{"code": "TEST-BAD", "description": "Prezzo errato", "purchase_price": 100, "sale_price": 50}'
check "Prezzo vendita < acquisto → 422" "422" "$HTTP_CODE" "$BODY"

# 5.12 Alert scorte basse
api GET "$API/parts/low-stock"
check "Alert scorte basse" "200" "$HTTP_CODE" "$BODY"

# ============================================================================
# 6. ORDINI DI LAVORO
# ============================================================================
echo ""
echo -e "${CYAN}━━━ 6. ORDINI DI LAVORO ━━━${NC}"

# 6.1 Crea ordine di lavoro (tutti i campi + voci iniziali)
api POST "$API/work-orders/" "{
    \"client_id\": \"$CLIENT_PF_ID\",
    \"vehicle_id\": \"$VEHICLE_ID\",
    \"problem_description\": \"Tagliando completo 45.000 km: cambio olio, filtro olio, controllo freni\",
    \"estimated_delivery\": \"2026-03-15\",
    \"km_in\": 45000,
    \"notes\": \"Cliente abituale, verificare anche livello liquido raffreddamento\",
    \"items\": [
        {
            \"description\": \"Manodopera tagliando\",
            \"quantity\": 2,
            \"unit_price\": 45.00,
            \"item_type\": \"labor\",
            \"technician_id\": \"$TECH_ID\"
        },
        {
            \"description\": \"Diagnosi elettronica\",
            \"quantity\": 1,
            \"unit_price\": 30.00,
            \"item_type\": \"service\"
        }
    ]
}"
check "Crea ordine di lavoro" "201" "$HTTP_CODE" "$BODY"
WO_ID=$(extract_id "$BODY")
echo "    → WO_ID=$WO_ID"

# 6.2 Lista ordini
api GET "$API/work-orders/?page=1&per_page=10"
check "Lista ordini" "200" "$HTTP_CODE" "$BODY"

# 6.3 Dettaglio ordine
api GET "$API/work-orders/$WO_ID"
check "Dettaglio ordine" "200" "$HTTP_CODE" "$BODY"

# 6.4 Filtra per stato
api GET "$API/work-orders/?status=draft"
check "Filtra ordini per stato" "200" "$HTTP_CODE" "$BODY"

# 6.5 Filtra per cliente
api GET "$API/work-orders/?client_id=$CLIENT_PF_ID"
check "Filtra ordini per cliente" "200" "$HTTP_CODE" "$BODY"

# 6.6 Aggiorna ordine
api PUT "$API/work-orders/$WO_ID" '{"notes": "Aggiunta nota: controllare anche tergicristalli", "km_in": 45010}'
check "Aggiorna ordine" "200" "$HTTP_CODE" "$BODY"

# 6.7 Aggiungi voce di lavoro
api POST "$API/work-orders/$WO_ID/items" "{
    \"description\": \"Sostituzione tergicristalli\",
    \"quantity\": 1,
    \"unit_price\": 20.00,
    \"item_type\": \"service\",
    \"technician_id\": \"$TECH_ID\"
}"
check "Aggiungi voce lavoro" "201" "$HTTP_CODE" "$BODY"
ITEM_ID=$(extract_id "$BODY")
echo "    → ITEM_ID=$ITEM_ID"

# 6.8 Aggiorna voce di lavoro
api PUT "$API/work-orders/$WO_ID/items/$ITEM_ID" '{"quantity": 2, "unit_price": 25.00}'
check "Aggiorna voce lavoro" "200" "$HTTP_CODE" "$BODY"

# 6.9 Aggiungi ricambio all'ordine
api POST "$API/work-orders/$WO_ID/parts" "{
    \"part_id\": \"$PART_ID\",
    \"quantity\": 1,
    \"unit_price\": 15.00
}"
check "Aggiungi ricambio all'ordine" "201" "$HTTP_CODE" "$BODY"
PART_USAGE_ID=$(extract_id "$BODY")
echo "    → PART_USAGE_ID=$PART_USAGE_ID"

# 6.10 Aggiungi olio all'ordine
api POST "$API/work-orders/$WO_ID/parts" "{
    \"part_id\": \"$PART_OIL_ID\",
    \"quantity\": 4,
    \"unit_price\": 40.00
}"
check "Aggiungi olio all'ordine" "201" "$HTTP_CODE" "$BODY"

# 6.11 Lista ricambi dell'ordine
api GET "$API/work-orders/$WO_ID/parts"
check "Lista ricambi ordine" "200" "$HTTP_CODE" "$BODY"

# 6.12 Cambio stato: draft → in_progress
api PATCH "$API/work-orders/$WO_ID/status" '{"status": "in_progress"}'
check "Stato → in_progress" "200" "$HTTP_CODE" "$BODY"

# 6.13 Cambio stato: in_progress → completed
api PATCH "$API/work-orders/$WO_ID/status" '{"status": "completed"}'
check "Stato → completed" "200" "$HTTP_CODE" "$BODY"

# 6.14 Edge case: transizione non valida (completed → draft)
api PATCH "$API/work-orders/$WO_ID/status" '{"status": "draft"}'
check "Transizione non valida → 400/422" "422" "$HTTP_CODE" "$BODY"

# ============================================================================
# 7. FATTURE
# ============================================================================
echo ""
echo -e "${CYAN}━━━ 7. FATTURE ━━━${NC}"

# 7.1 Crea fattura da ordine completato
api POST "$API/invoices/from-work-order/$WO_ID" '{
    "invoice_date": "2026-02-21",
    "customer_notes": "Grazie per la fiducia!"
}'
check "Crea fattura da WO" "201" "$HTTP_CODE" "$BODY"
# Il response è InvoiceCreationResponse con campo "invoice"
INVOICE_ID=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('invoice',d).get('id',d.get('id','')))" 2>/dev/null)
INVOICE_NUMBER=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('invoice',d).get('invoice_number',d.get('invoice_number','')))" 2>/dev/null)
echo "    → INVOICE_ID=$INVOICE_ID"
echo "    → INVOICE_NUMBER=$INVOICE_NUMBER"

# 7.2 Lista fatture
api GET "$API/invoices/?page=1&per_page=10"
check "Lista fatture" "200" "$HTTP_CODE" "$BODY"

# 7.3 Dettaglio fattura
api GET "$API/invoices/$INVOICE_ID"
check "Dettaglio fattura" "200" "$HTTP_CODE" "$BODY"

# 7.4 Filtra fatture per cliente
api GET "$API/invoices/?client_id=$CLIENT_PF_ID"
check "Filtra fatture per cliente" "200" "$HTTP_CODE" "$BODY"

# 7.5 Filtra fatture per stato
api GET "$API/invoices/?status=unpaid"
check "Filtra fatture per stato" "200" "$HTTP_CODE" "$BODY"

# 7.6 Fatture scadute
api GET "$API/invoices/?overdue_only=true"
check "Fatture scadute" "200" "$HTTP_CODE" "$BODY"

# 7.7 Aggiorna fattura (note)
api PUT "$API/invoices/$INVOICE_ID" '{"notes": "Nota interna aggiornata", "customer_notes": "Attenzione: scadenza prossima"}'
check "Aggiorna fattura" "200" "$HTTP_CODE" "$BODY"

# 7.8 Edge case: fattura doppia sullo stesso ordine
api POST "$API/invoices/from-work-order/$WO_ID" '{}'
check "Fattura doppia → 400/422" "422" "$HTTP_CODE" "$BODY"

# 7.9 Report incassi
api GET "$API/invoices/reports/revenue?from_date=2026-01-01&to_date=2026-12-31"
check "Report incassi" "200" "$HTTP_CODE" "$BODY"

# ============================================================================
# 8. PAGAMENTI
# ============================================================================
echo ""
echo -e "${CYAN}━━━ 8. PAGAMENTI ━━━${NC}"

# 8.1 Crea pagamento con allocazione FIFO
api POST "$API/invoices/payments" "{
    \"client_id\": \"$CLIENT_PF_ID\",
    \"amount\": 100.00,
    \"payment_date\": \"2026-02-21\",
    \"payment_method\": \"cash\",
    \"reference\": \"Contanti ricevuti\",
    \"notes\": \"Acconto su fattura\",
    \"allocation_strategy\": \"fifo\"
}"
check "Crea pagamento FIFO" "201" "$HTTP_CODE" "$BODY"
PAYMENT_ID=$(extract_id "$BODY")
echo "    → PAYMENT_ID=$PAYMENT_ID"

# 8.2 Crea pagamento con allocazione manuale
api POST "$API/invoices/payments" "{
    \"client_id\": \"$CLIENT_PF_ID\",
    \"amount\": 50.00,
    \"payment_date\": \"2026-02-21\",
    \"payment_method\": \"pos\",
    \"reference\": \"POS #12345\",
    \"allocation_strategy\": \"manual\",
    \"allocations\": [
        {\"invoice_id\": \"$INVOICE_ID\", \"amount\": 50.00}
    ]
}"
check "Crea pagamento manuale" "201" "$HTTP_CODE" "$BODY"

# 8.3 Lista pagamenti per cliente
api GET "$API/invoices/clients/$CLIENT_PF_ID/payments"
check "Lista pagamenti per cliente" "200" "$HTTP_CODE" "$BODY"

# 8.4 Dettaglio pagamento
api GET "$API/invoices/payments/$PAYMENT_ID"
check "Dettaglio pagamento" "200" "$HTTP_CODE" "$BODY"

# 8.5 Edge case: pagamento con data futura
api POST "$API/invoices/payments" "{
    \"client_id\": \"$CLIENT_PF_ID\",
    \"amount\": 10.00,
    \"payment_date\": \"2030-01-01\",
    \"payment_method\": \"cash\"
}"
check "Pagamento data futura → 422" "422" "$HTTP_CODE" "$BODY"

# 8.6 Edge case: importo negativo
api POST "$API/invoices/payments" "{
    \"client_id\": \"$CLIENT_PF_ID\",
    \"amount\": -50.00,
    \"payment_date\": \"2026-02-21\",
    \"payment_method\": \"cash\"
}"
check "Pagamento importo negativo → 422" "422" "$HTTP_CODE" "$BODY"

# ============================================================================
# 9. CAPARRE/ACCONTI (DEPOSITS)
# ============================================================================
echo ""
echo -e "${CYAN}━━━ 9. CAPARRE/ACCONTI ━━━${NC}"

# 9.1 Crea caparra
api POST "$API/deposits/" "{
    \"client_id\": \"$CLIENT_PF_ID\",
    \"work_order_id\": null,
    \"amount\": 200.00,
    \"payment_method\": \"cash\",
    \"deposit_date\": \"2026-02-21\",
    \"reference\": \"Acconto generico\",
    \"notes\": \"Acconto per lavori futuri\"
}"
check "Crea caparra" "200" "$HTTP_CODE" "$BODY"
DEPOSIT_ID=$(extract_id "$BODY")
echo "    → DEPOSIT_ID=$DEPOSIT_ID"

# 9.2 Lista caparre per cliente
api GET "$API/deposits/client/$CLIENT_PF_ID"
check "Lista caparre per cliente" "200" "$HTTP_CODE" "$BODY"

# 9.3 Dettaglio caparra
api GET "$API/deposits/$DEPOSIT_ID"
check "Dettaglio caparra" "200" "$HTTP_CODE" "$BODY"

# 9.4 Applica caparra a fattura
api POST "$API/deposits/$DEPOSIT_ID/apply/$INVOICE_ID"
check "Applica caparra a fattura" "200" "$HTTP_CODE" "$BODY"

# 9.5 Crea caparra per rimborso
api POST "$API/deposits/" "{
    \"client_id\": \"$CLIENT_PF_ID\",
    \"amount\": 50.00,
    \"payment_method\": \"pos\",
    \"deposit_date\": \"2026-02-21\",
    \"notes\": \"Caparra da rimborsare\"
}"
check "Crea caparra per rimborso" "200" "$HTTP_CODE" "$BODY"
DEPOSIT_REFUND_ID=$(extract_id "$BODY")

# 9.6 Rimborsa caparra
api POST "$API/deposits/$DEPOSIT_REFUND_ID/refund"
check "Rimborsa caparra" "200" "$HTTP_CODE" "$BODY"

# ============================================================================
# 10. DICHIARAZIONI DI INTENTO
# ============================================================================
echo ""
echo -e "${CYAN}━━━ 10. DICHIARAZIONI DI INTENTO ━━━${NC}"

# 10.1 Crea dichiarazione (tutti i campi)
api POST "$API/intent-declarations/" "{
    \"client_id\": \"$CLIENT_PF_ID\",
    \"protocol_number\": \"PROT-2026-T001\",
    \"declaration_date\": \"2026-01-15\",
    \"amount_limit\": 50000.00,
    \"expiry_date\": \"2026-12-31\",
    \"is_active\": true,
    \"notes\": \"Dichiarazione test annuale\"
}"
check "Crea dichiarazione intento" "201" "$HTTP_CODE" "$BODY"
INTENT_ID=$(extract_id "$BODY")
echo "    → INTENT_ID=$INTENT_ID"

# 10.2 Lista dichiarazioni
api GET "$API/intent-declarations/?page=1&per_page=10"
check "Lista dichiarazioni" "200" "$HTTP_CODE" "$BODY"

# 10.3 Dettaglio dichiarazione
api GET "$API/intent-declarations/$INTENT_ID"
check "Dettaglio dichiarazione" "200" "$HTTP_CODE" "$BODY"

# 10.4 Dichiarazioni per cliente
api GET "$API/intent-declarations/client/$CLIENT_PF_ID"
check "Dichiarazioni per cliente" "200" "$HTTP_CODE" "$BODY"

# 10.5 Aggiorna dichiarazione
api PUT "$API/intent-declarations/$INTENT_ID" '{
    "notes": "Nota aggiornata",
    "amount_limit": 60000.00
}'
check "Aggiorna dichiarazione" "200" "$HTTP_CODE" "$BODY"

# 10.6 Disattiva dichiarazione
api PUT "$API/intent-declarations/$INTENT_ID" '{"is_active": false}'
check "Disattiva dichiarazione" "200" "$HTTP_CODE" "$BODY"

# 10.7 Edge case: amount_limit negativo
api POST "$API/intent-declarations/" "{
    \"client_id\": \"$CLIENT_PF_ID\",
    \"protocol_number\": \"PROT-BAD\",
    \"declaration_date\": \"2026-01-01\",
    \"amount_limit\": -100,
    \"expiry_date\": \"2026-12-31\"
}"
check "Amount limit negativo → 422" "422" "$HTTP_CODE" "$BODY"

# 10.8 Edge case: cliente inesistente
api POST "$API/intent-declarations/" '{
    "client_id": "00000000-0000-0000-0000-000000000000",
    "protocol_number": "PROT-BAD",
    "declaration_date": "2026-01-01",
    "amount_limit": 1000,
    "expiry_date": "2026-12-31"
}'
check "Dichiarazione cliente inesist → 404" "404" "$HTTP_CODE" "$BODY"

# 10.9 Elimina dichiarazione
api DELETE "$API/intent-declarations/$INTENT_ID"
check "Elimina dichiarazione" "204" "$HTTP_CODE" "$BODY"

# ============================================================================
# 11. NOTE DI CREDITO
# ============================================================================
echo ""
echo -e "${CYAN}━━━ 11. NOTE DI CREDITO ━━━${NC}"

# 11.1 Nota di credito totale
api POST "$API/invoices/$INVOICE_ID/credit-notes?reason=Errore%20fatturazione%20storno%20totale" ""
check "Nota credito totale" "201" "$HTTP_CODE" "$BODY"
if [ "$HTTP_CODE" == "201" ]; then
    CN_ID=$(extract_id "$BODY")
    echo "    → CN_ID=$CN_ID"

    # 11.2 Lista note di credito
    api GET "$API/credit-notes/"
    check "Lista note credito" "200" "$HTTP_CODE" "$BODY"

    # 11.3 Dettaglio nota di credito
    api GET "$API/credit-notes/$CN_ID"
    check "Dettaglio nota credito" "200" "$HTTP_CODE" "$BODY"
else
    echo -e "  ${YELLOW}⚠ Saltate sotto-test note credito (creazione fallita)${NC}"
    WARN=$((WARN+1))
fi

# ============================================================================
# 12. CHIUSURA CASSA
# ============================================================================
echo ""
echo -e "${CYAN}━━━ 12. CHIUSURA CASSA ━━━${NC}"

# 12.1 Anteprima cassa
api GET "$API/cash-register/preview/2026-02-21"
check "Anteprima cassa" "200" "$HTTP_CODE" "$BODY"

# 12.2 Chiudi cassa
api POST "$API/cash-register/close" '{
    "close_date": "2026-02-21",
    "closed_by": "Corrado",
    "notes": "Chiusura test automatico"
}'
check "Chiudi cassa" "200" "$HTTP_CODE" "$BODY"

# 12.3 Storico chiusure
api GET "$API/cash-register/history?from_date=2026-01-01&to_date=2026-12-31"
check "Storico chiusure" "200" "$HTTP_CODE" "$BODY"

# 12.4 Dettaglio chiusura per data
api GET "$API/cash-register/2026-02-21"
check "Dettaglio chiusura" "200" "$HTTP_CODE" "$BODY"

# 12.5 Riconcilia cassa
api PATCH "$API/cash-register/2026-02-21/reconcile"
check "Riconcilia cassa" "200" "$HTTP_CODE" "$BODY"

# 12.6 Edge case: chiusura duplicata
api POST "$API/cash-register/close" '{
    "close_date": "2026-02-21",
    "closed_by": "Corrado"
}'
check "Chiusura duplicata → 400/409/422" "422" "$HTTP_CODE" "$BODY"

# ============================================================================
# 13. FLUSSO COMPLETO: SECONDO ORDINE (per azienda)
# ============================================================================
echo ""
echo -e "${CYAN}━━━ 13. FLUSSO END-TO-END (Azienda) ━━━${NC}"

# 13.1 Crea ordine per azienda
api POST "$API/work-orders/" "{
    \"client_id\": \"$CLIENT_AZ_ID\",
    \"vehicle_id\": \"$VEHICLE_AZ_ID\",
    \"problem_description\": \"Revisione completa furgone aziendale con sostituzione pastiglie freni\",
    \"km_in\": 120500,
    \"items\": [
        {\"description\": \"Revisione completa\", \"quantity\": 4, \"unit_price\": 50.00, \"item_type\": \"labor\"},
        {\"description\": \"Sostituzione pastiglie\", \"quantity\": 1, \"unit_price\": 80.00, \"item_type\": \"service\"}
    ]
}"
check "Crea ordine azienda" "201" "$HTTP_CODE" "$BODY"
WO2_ID=$(extract_id "$BODY")
echo "    → WO2_ID=$WO2_ID"

# 13.2 Avanza stato
api PATCH "$API/work-orders/$WO2_ID/status" '{"status": "in_progress"}'
check "Stato azienda → in_progress" "200" "$HTTP_CODE" "$BODY"

api PATCH "$API/work-orders/$WO2_ID/status" '{"status": "completed"}'
check "Stato azienda → completed" "200" "$HTTP_CODE" "$BODY"

# 13.3 Crea fattura con fatturazione a terzi
api POST "$API/invoices/from-work-order/$WO2_ID" "{
    \"invoice_date\": \"2026-02-21\",
    \"bill_to_client_id\": \"$CLIENT_PF_ID\",
    \"claim_number\": \"CLAIM-2026-001\",
    \"customer_notes\": \"Fattura a terzi per Bianchi Srl\"
}"
check "Fattura a terzi" "201" "$HTTP_CODE" "$BODY"
INVOICE2_ID=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('invoice',d).get('id',d.get('id','')))" 2>/dev/null)
echo "    → INVOICE2_ID=$INVOICE2_ID"

# ============================================================================
# 14. CLEANUP (opzionale) - Elimina risorse create
# ============================================================================
echo ""
echo -e "${CYAN}━━━ 14. CLEANUP (eliminazioni) ━━━${NC}"

# 14.1 Elimina voce lavoro
api DELETE "$API/work-orders/$WO2_ID/items/$ITEM_ID"
# Potrebbe dare 404 se l'item appartiene al WO1
if [ "$HTTP_CODE" == "204" ] || [ "$HTTP_CODE" == "404" ]; then
    echo -e "  ${GREEN}✓ OK${NC} Elimina voce lavoro (HTTP $HTTP_CODE)"
    PASS=$((PASS+1))
else
    echo -e "  ${RED}✗ FAIL${NC} Elimina voce lavoro — HTTP $HTTP_CODE"
    FAIL=$((FAIL+1))
fi

# 14.2 Elimina tecnico
api DELETE "$API/technicians/$TECH_ID"
check "Elimina tecnico" "204" "$HTTP_CODE" "$BODY"

# 14.3 Edge case: elimina cliente con fatture (dovrebbe fallire)
api DELETE "$API/clients/$CLIENT_PF_ID"
if [ "$HTTP_CODE" == "400" ] || [ "$HTTP_CODE" == "409" ] || [ "$HTTP_CODE" == "422" ]; then
    echo -e "  ${GREEN}✓ PASS${NC} Elimina cliente con fatture → rifiutato (HTTP $HTTP_CODE)"
    PASS=$((PASS+1))
elif [ "$HTTP_CODE" == "204" ]; then
    echo -e "  ${YELLOW}⚠ WARN${NC} Cliente con fatture eliminato senza errore (cascata?)"
    WARN=$((WARN+1))
else
    echo -e "  ${RED}✗ FAIL${NC} Elimina cliente con fatture — HTTP $HTTP_CODE inatteso"
    FAIL=$((FAIL+1))
fi


# ============================================================================
# RIEPILOGO FINALE
# ============================================================================
echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║                    RIEPILOGO TEST                           ║${NC}"
echo -e "${BOLD}╠══════════════════════════════════════════════════════════════╣${NC}"
TOTAL=$((PASS + FAIL))
echo -e "${BOLD}║  ${GREEN}Passati:  $PASS${NC}${BOLD}                                               ║${NC}"
echo -e "${BOLD}║  ${RED}Falliti:  $FAIL${NC}${BOLD}                                               ║${NC}"
echo -e "${BOLD}║  ${YELLOW}Warning:  $WARN${NC}${BOLD}                                               ║${NC}"
echo -e "${BOLD}║  Totale:   $TOTAL                                               ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"

if [ $FAIL -gt 0 ]; then
    echo ""
    echo -e "${RED}Errori riscontrati:${NC}"
    echo -e "$ERRORS"
    echo ""
    exit 1
else
    echo ""
    echo -e "${GREEN}🎉 Tutti i test sono passati!${NC}"
    echo ""
    exit 0
fi
