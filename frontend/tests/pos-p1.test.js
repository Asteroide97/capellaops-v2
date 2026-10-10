import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const page = readFileSync(new URL('../src/pages/PosPage.jsx', import.meta.url), 'utf8').replace(/\r\n/g, '\n');
function code(start, end) {
  const at = page.indexOf(start);
  assert.ok(at >= 0, `Missing actual handler: ${start}`);
  const until = page.indexOf(end, at);
  assert.ok(until >= 0, `Missing end: ${end}`);
  return page.slice(at, until).trim();
}
function helper(name, end, context = {}) { return runInNewContext(`(${code(name, end)})`, context); }
function deferred() { let resolve, reject; const promise = new Promise((a, b) => {resolve=a; reject=b;}); return {promise, resolve, reject}; }

test('F04 opening input preserves negative sign and invalid text until validation', () => {
  const form = page.slice(page.indexOf('<h2>Abrir caja'));
  const expression = form.match(/fondo_inicial: (.+),/)[1];
  const normalizeDecimalInput = helper('function normalizeDecimalInput', page.includes('function parseOpeningFund') ? '\nfunction parseOpeningFund' : '\nfunction createCartLineId');
  for (const value of ['-1', '-0.01', 'invalid']) {
    assert.equal(runInNewContext(expression, {event: {target: {value}}, normalizeDecimalInput}), value);
  }
});

function openingFixture(value, wait = null) {
  const state = {calls: [], error: '', success: '', cleared: false};
  const context = {
    selectedWarehouseId: 'A', warehouseContextReady: true, openShiftForm: {fondo_inicial: value, notas: 'Synthetic'},
    openShiftRequestRef: {current: false}, token: 'fixture', empresaId: 'T', defaultOpenShiftForm: {},
    warehouseScopeRef: {current: {warehouseId: 'A'}}, isCurrentWarehouseContext: () => true,
    setError: v => {state.error=v;}, setOpenShiftError: v => {state.error=v;},
    setShiftSubmitting() {}, clearFeedback: () => {state.error=''; state.success='';},
    setActiveShift() {}, setOpenShiftForm: () => {state.cleared=true;},
    refreshPosData: async () => {}, setSuccess: v => {state.success=v;}, updateView() {},
    getPosUiError: (e, fallback) => e.message || fallback,
    openPosShift: async request => {state.calls.push(request); if (wait) await wait.promise; return {id:'SHIFT', almacen_id:'A'};},
  };
  if (page.includes('function parseOpeningFund')) context.parseOpeningFund = helper('function parseOpeningFund', '\n\nfunction');
  return {state, submit: helper('async function handleOpenShift', '\n  function openShiftMovementModal', context)};
}

test('F04 zero/positive/empty retain existing opening contract', async () => {
  for (const [value, amount] of [['0', 0], ['1', 1], ['10.50', 10.5], ['', 0]]) {
    const {state, submit} = openingFixture(value);
    await submit({preventDefault() {}});
    assert.equal(state.calls.length, 1);
    assert.equal(Number(state.calls[0].payload.fondo_inicial), amount);
    assert.equal(state.error, '');
  }
});

test('F04 invalid/negative blocks API, retains form and displays a localized error', async () => {
  for (const value of ['-1', '-0.01', 'invalid', '1bad2']) {
    const {state, submit} = openingFixture(value);
    await submit({preventDefault() {}});
    assert.equal(state.calls.length, 0);
    assert.equal(state.cleared, false);
    assert.equal(state.success, '');
    assert.ok(state.error);
  }
  assert.ok(page.includes('id="pos-open-shift-error" role="alert"'));
});

test('F04 immediate double submit sends one request', async () => {
  const wait=deferred();
  const {state, submit}=openingFixture('1', wait);
  const first=submit({preventDefault() {}});
  const second=submit({preventDefault() {}});
  wait.resolve();
  await Promise.all([first,second]);
  assert.equal(state.calls.length,1);
});

test('F04 retains previous cents-only step validity without rounding input', async () => {
  const valid=openingFixture('10.5000');
  await valid.submit({preventDefault() {}}); assert.equal(valid.state.calls.length,1);
  const invalid=openingFixture('10.501');
  await invalid.submit({preventDefault() {}});
  assert.equal(invalid.state.calls.length,0); assert.equal(invalid.state.cleared,false); assert.ok(invalid.state.error);
});

function warehouseFixture(lines = [{tipo_linea:'material', material_id:'M', cantidad:'2', precio_unitario:'10.01', descuento_unitario:'0.02', impuesto_tasa:'0.16'}]) {
  const state={warehouse:'A', cart:structuredClone(lines), pending:'', error:'', modalError:'', scopeState:{}, catalog:[], shift:null, api:[], clears:0};
  const context={
    token:'fixture', empresaId:'T', warehouseScopeRef:{current:{warehouseId:'A', empresaId:'T', token:'fixture', generation:0}},
    catalogRequestRef:{current:0}, shiftRequestRef:{current:0}, warehouseChangeRequestRef:{current:false}, openShiftRequestRef:{current:false},
    submitting:false, shiftSubmitting:false, editableSaleSubmitting:false, editableSaleLoading:false, editableSaleRecalculating:false,
    catalogFilters:{}, DEFAULT_PAGE_SIZE:25, saleFilters:{}, resumedSaleId:'', saleForm:{descuento_global:'1', notas:'Synthetic'},
    usesMixedPayments:false, paymentRows:[], cartHasInvalidQuantity:false, cartHasInvalidDiscount:false, cartHasMissingManualDescription:false,
    setSelectedWarehouseId:v=>{state.warehouse=v;}, setPendingWarehouseId:v=>{state.pending=v;},
    setWarehouseChangeError:v=>{state.modalError=v;}, setWarehouseChangeSubmitting() {},
    setWarehouseContext:v=>{state.scopeState=v;}, setActiveShift:v=>{state.shift=v;}, setCatalogItems:v=>{state.catalog=v;}, setCatalogMeta() {},
    setError:v=>{state.error=v;}, setSuccess() {}, setSuccessContext() {}, setSubmitting() {},
    setSelectedSale() {}, setSelectedTicket() {}, setResumedSaleId() {}, updateView() {},
    clearFeedback:()=>{state.error='';}, clearCart:()=>{state.cart=[]; state.clears++;},
    refreshPosData:async()=>{}, loadSales:async()=>{},
    isInventoryTrackedLine:line=>(line.tipo_linea||'material')==='material', getSaleLineDisplayName:line=>line.descripcion,
    getPosUiError:(e,fallback)=>e.message||fallback,
    suspendPosSale:async request=>{state.api.push(request); return {id:'SUSPENDED',folio:'QA-SUSPENDED',details:request.payload.items};},
  };
  Object.defineProperties(context, {
    selectedWarehouseId:{get:()=>state.warehouse}, selectedWarehouse:{get:()=>({id:state.warehouse})},
    cart:{get:()=>state.cart}, hasCartItems:{get:()=>state.cart.length>0}, pendingWarehouseId:{get:()=>state.pending},
  });
  for (const [name, start, end] of [
    ['isCurrentWarehouseContext','function isCurrentWarehouseContext','\n  function beginWarehouseContext'],
    ['beginWarehouseContext','function beginWarehouseContext','\n  function markWarehouseContextReady'],
    ['markWarehouseContextReady','function markWarehouseContextReady','\n  function selectWarehouse'],
    ['selectWarehouse','function selectWarehouse','\n  function applyWarehouseChange'],
    ['applyWarehouseChange','function applyWarehouseChange','\n  function requestWarehouseChange'],
    ['requestWarehouseChange','function requestWarehouseChange','\n  function cancelWarehouseChange'],
    ['cancelWarehouseChange','function cancelWarehouseChange','\n  async function confirmWarehouseChange'],
    ['confirmWarehouseChange','async function confirmWarehouseChange','\n  async function loadWarehousesOptions'],
    ['loadActiveShift','async function loadActiveShift','\n  async function loadCatalog'],
    ['loadCatalog','async function loadCatalog','\n  async function loadWarehouseContext'],
    ['loadWarehouseContext','async function loadWarehouseContext','\n  async function loadSales'],
    ['handleSuspendSale','async function handleSuspendSale','\n  async function handleResumeSale'],
  ]) context[name]=helper(start,end,context);
  return {state, context};
}

test('F05 empty cart changes directly; nonempty cart opens confirmation without clearing', () => {
  const empty=warehouseFixture([]); empty.context.requestWarehouseChange('B');
  assert.equal(empty.state.warehouse,'B'); assert.equal(empty.state.pending,'');
  const full=warehouseFixture(); full.context.requestWarehouseChange('B');
  assert.equal(full.state.warehouse,'A'); assert.equal(full.state.cart.length,1); assert.equal(full.state.pending,'B');
});

test('F05 cancel preserves warehouse/cart and discard explicitly clears them', async () => {
  const {state, context}=warehouseFixture(); const original=JSON.stringify(state.cart);
  context.requestWarehouseChange('B'); context.cancelWarehouseChange();
  assert.equal(state.warehouse,'A'); assert.equal(JSON.stringify(state.cart),original);
  context.requestWarehouseChange('B'); await context.confirmWarehouseChange('discard');
  assert.equal(state.warehouse,'B'); assert.equal(state.cart.length,0); assert.equal(state.api.length,0);
});

test('F05 suspend uses existing handler/payload then changes; failure retains work', async () => {
  const {state, context}=warehouseFixture();
  context.requestWarehouseChange('B'); await context.confirmWarehouseChange('suspend');
  assert.equal(state.api.length,1); assert.equal(state.api[0].payload.almacen_id,'A');
  assert.equal(state.api[0].payload.items[0].cantidad,'2'); assert.equal(state.api[0].payload.items[0].precio_unitario,'10.01');
  assert.equal(state.warehouse,'B'); assert.equal(state.cart.length,0);
  const failed=warehouseFixture(); const original=JSON.stringify(failed.state.cart);
  failed.context.suspendPosSale=async()=>{throw new Error('Synthetic suspension failure');};
  failed.context.requestWarehouseChange('B'); await failed.context.confirmWarehouseChange('suspend');
  assert.equal(failed.state.warehouse,'A'); assert.equal(JSON.stringify(failed.state.cart),original);
  assert.equal(failed.state.pending,'B'); assert.ok(failed.state.modalError);
});

test('F05 context loading and late old responses cannot replace new warehouse data', async () => {
  const {state, context}=warehouseFixture([]);
  const oldCatalog=deferred(), oldShift=deferred();
  context.getPosCatalog=({almacenId})=>almacenId==='A'?oldCatalog.promise:Promise.resolve({items:[{material_id:'B'}],total:1});
  context.getPosActiveShift=({warehouseId})=>warehouseId==='A'?oldShift.promise:Promise.resolve({active_shift:{id:'SHIFT-B',almacen_id:'B'}});
  const old=context.loadWarehouseContext('A');
  assert.equal(state.scopeState.status,'loading');
  context.requestWarehouseChange('B'); await context.loadWarehouseContext('B');
  assert.equal(state.scopeState.status,'ready'); assert.equal(state.shift.almacen_id,'B');
  oldCatalog.resolve({items:[{material_id:'A'}],total:1}); oldShift.resolve({active_shift:{id:'SHIFT-A',almacen_id:'A'}});
  await old;
  assert.equal(state.catalog[0].material_id,'B'); assert.equal(state.shift.almacen_id,'B');
});

test('F05 no-shift/error context remains safe and same-warehouse request leaves cart unchanged', async () => {
  const {state, context}=warehouseFixture(); const original=JSON.stringify(state.cart);
  context.requestWarehouseChange('A'); assert.equal(JSON.stringify(state.cart),original); assert.equal(state.pending,'');
  context.getPosCatalog=async()=>({items:[],total:0}); context.getPosActiveShift=async()=>({active_shift:null});
  await context.loadWarehouseContext('A'); assert.equal(state.shift,null); assert.equal(state.scopeState.status,'ready');
  context.getPosCatalog=async()=>{throw new Error('Synthetic context failure');};
  await context.loadWarehouseContext('A'); assert.equal(state.scopeState.status,'error');
  assert.ok(page.includes('!warehouseContextReady'));
  assert.ok(page.includes('disabled={!canCharge || submitting}'));
});

test('F05 immediate double suspend confirmation does not duplicate the suspended sale', async () => {
  const {state, context}=warehouseFixture(); const wait=deferred();
  context.suspendPosSale=async request=>{state.api.push(request); await wait.promise; return {id:'S',folio:'QA'};};
  context.requestWarehouseChange('B');
  const first=context.confirmWarehouseChange('suspend');
  const second=context.confirmWarehouseChange('suspend');
  assert.equal(state.warehouse,'A'); assert.equal(state.cart.length,1);
  wait.resolve(); await Promise.all([first,second]);
  assert.equal(state.api.length,1); assert.equal(state.warehouse,'B');
});

test('F05 late old failure cannot replace the loaded context or its feedback', async () => {
  const {state, context}=warehouseFixture([]); const old=deferred();
  context.getPosCatalog=({almacenId})=>almacenId==='A'?old.promise:Promise.resolve({items:[{material_id:'B'}]});
  context.getPosActiveShift=async({warehouseId})=>({active_shift:{id:'SHIFT-'+warehouseId,almacen_id:warehouseId}});
  const pending=context.loadWarehouseContext('A');
  context.requestWarehouseChange('B'); await context.loadWarehouseContext('B');
  old.reject(new Error('Old warehouse failure')); await pending;
  assert.equal(state.scopeState.status,'ready'); assert.equal(state.error,''); assert.equal(state.catalog[0].material_id,'B');
});

test('F05 actual charge guard blocks loading/pending/error context before either payment API', async () => {
  const submitCode=code('async function handleCreateSale','\n  async function handleOpenShift');
  for(const flags of [{warehouseContextReady:false,pendingWarehouseId:'',warehouseChangeSubmitting:false},
    {warehouseContextReady:true,pendingWarehouseId:'B',warehouseChangeSubmitting:false},
    {warehouseContextReady:true,pendingWarehouseId:'',warehouseChangeSubmitting:true}]) {
    let calls=0, message='';
    const submit=runInNewContext(`(${submitCode})`, {...flags, setError:v=>{message=v;},
      createPosSale:async()=>{calls++;}, paySuspendedPosSale:async()=>{calls++;}});
    await submit({preventDefault() {}});
    assert.equal(calls,0); assert.ok(message);
  }
});

test('F05 actual charge eligibility requires matching loaded shift and context', () => {
  const shiftExpression=page.match(/const hasActiveShift = (.*);/)[1];
  const chargeExpression=page.slice(page.indexOf('const canCharge =')+'const canCharge ='.length, page.indexOf('\n  const paymentState'));
  for(const [ready,shift,expected] of [[false,{id:'S',almacen_id:'B'},false],
    [true,null,false],[true,{id:'S',almacen_id:'A'},false],[true,{id:'S',almacen_id:'B'},true]]) {
    const hasActiveShift=runInNewContext(shiftExpression,{warehouseContextReady:ready, activeShift:shift, selectedWarehouseId:'B'});
    const canCharge=runInNewContext(chargeExpression.trim().replace(/;$/, ''),{Boolean,selectedWarehouseId:'B',
      warehouseContextReady:ready,hasActiveShift,hasCartItems:true,pendingWarehouseId:'',warehouseChangeSubmitting:false,
      cartHasInvalidQuantity:false,cartHasInvalidDiscount:false,cartHasMissingPrice:false,cartHasMissingManualDescription:false,
      cartHasInvalidPayments:false,paidPreview:20,cartTotal:20,usesMixedPayments:false,nonCashOverageWithoutCash:false,hasMixedPaymentRows:false});
    assert.equal(canCharge,expected);
  }
});

test('F05 tabs change the view without clearing the current cart', () => {
  let updated;
  const navigate=helper('function updateView','\n  function clearFeedback', {
    URLSearchParams, searchParams:new URLSearchParams('view=sell'),setSearchParams:value=>{updated=value;},
    clearCart:()=>{throw new Error('Navigation must not discard cart');},
  });
  navigate('history'); assert.equal(updated.get('view'),'history');
});

test('F05 late old scanner lookup cannot add old lines or replace current feedback', async () => {
  const {state, context}=warehouseFixture([]); const old=deferred();
  context.setCatalogFilters=()=>{}; context.addToCart=()=>{throw new Error('Old material added');};
  context.getPosCatalog=({almacenId})=>almacenId==='A'?old.promise:Promise.resolve({items:[{material_id:'B'}]});
  context.getPosActiveShift=async({warehouseId})=>({active_shift:{id:'S-'+warehouseId,almacen_id:warehouseId}});
  const scan=helper('async function handleCatalogScan','\n  async function handleSalesSearch',context);
  const pending=scan('QA-SKU');
  context.requestWarehouseChange('B'); await context.loadWarehouseContext('B');
  old.resolve({items:[{material_id:'A',nombre:'Old material'}]}); await pending;
  assert.equal(state.error,''); assert.equal(state.cart.length,0); assert.equal(state.catalog[0].material_id,'B');
});

test('F05 resumed suspension reuses its existing ID without creating another sale', async () => {
  const {state, context}=warehouseFixture(); context.resumedSaleId='EXISTING-SUSPENDED';
  context.requestWarehouseChange('B'); await context.confirmWarehouseChange('suspend');
  assert.equal(state.api.length,0); assert.equal(state.warehouse,'B'); assert.equal(state.cart.length,0);
});

test('F05 context becomes ready only after both reads; empty warehouse never remains loading', async () => {
  const {state, context}=warehouseFixture([]); const shift=deferred();
  context.getPosCatalog=async()=>({items:[],total:0}); context.getPosActiveShift=()=>shift.promise;
  const pending=context.loadWarehouseContext('A'); await Promise.resolve(); await Promise.resolve();
  assert.equal(state.scopeState.status,'loading');
  shift.resolve({active_shift:null}); await pending; assert.equal(state.scopeState.status,'ready');
  context.selectWarehouse(''); await context.loadWarehouseContext('');
  assert.equal(state.scopeState.status,'empty');
});

test('F05 obsolete loader calls cannot invalidate the new warehouse in-flight requests', async () => {
  const {state,context}=warehouseFixture([]); const catalog=deferred(),shift=deferred();
  context.getPosCatalog=()=>catalog.promise; context.getPosActiveShift=()=>shift.promise;
  context.requestWarehouseChange('B'); const pending=context.loadWarehouseContext('B');
  await context.loadCatalog('A'); await context.loadActiveShift('A');
  catalog.resolve({items:[{material_id:'B'}],total:1}); shift.resolve({active_shift:{id:'SB',almacen_id:'B'}});
  await pending;
  assert.equal(state.scopeState.status,'ready'); assert.equal(state.catalog[0].material_id,'B'); assert.equal(state.shift.almacen_id,'B');
});

test('F05 failed latest search during context load cannot leave the screen permanently loading', async () => {
  const {state,context}=warehouseFixture([]); const first=deferred(); let calls=0;
  context.getPosCatalog=()=>++calls===1?first.promise:Promise.reject(new Error('Synthetic new search failure'));
  context.getPosActiveShift=async()=>({active_shift:null});
  const pending=context.loadWarehouseContext('A');
  await assert.rejects(context.loadCatalog('A',{q:'new'}));
  first.resolve({items:[]}); await pending;
  assert.equal(state.scopeState.status,'error');
});
