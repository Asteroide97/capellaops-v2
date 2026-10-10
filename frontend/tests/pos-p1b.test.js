import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {runInNewContext} from 'node:vm';
const require=createRequire(new URL('../package.json',import.meta.url));
const parser=require('@babel/parser');
const source=readFileSync(new URL('../src/pages/PosPage.jsx',import.meta.url),'utf8').replace(/\r\n/g,'\n');
function code(name,end){const at=source.indexOf(name);assert.ok(at>=0,`Missing ${name}`);return source.slice(at,source.indexOf(end,at)).trim();}
function actual(name,end,context={}){return runInNewContext(`(${code(name,end)})`,context);}
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return{promise,resolve,reject};}

test('F06 opening/reopening closing starts blank without copying expected or sending a request',()=>{
  let form={efectivo_contado:'90',notas:'Unconfirmed'},error='Previous',open=false;
  const context={defaultCloseShiftForm:{efectivo_contado:'',notas:''},cashActionRef:{current:''},
    setCloseShiftForm:v=>{form=v;},setCloseShiftError:v=>{error=v;},setCloseShiftModalOpen:v=>{open=v;}};
  const show=actual('function openCloseShiftModal','\n  function closeCloseShiftModal',context);
  const hide=actual('function closeCloseShiftModal','\n  async function handleCloseShiftSubmit',context);
  show();assert.equal(form.efectivo_contado,'');assert.equal(error,'');assert.equal(open,true);
  form.efectivo_contado='110';hide();show();assert.equal(form.efectivo_contado,'');
  assert.ok(!source.includes('efectivo_contado: expectedCash ?'));
});

test('F06 difference remains pending until explicit valid counted value',()=>{
  const parseOpeningFund=actual('function parseOpeningFund','\n\nfunction');
  const parseCountedCash=actual('function parseCountedCash','\n\nfunction',{parseOpeningFund});
  const expression=source.match(/const closeShiftDifference = (.*);/)[1];
  for(const[input,expected]of[['',null],['invalid',null],['-1',null],['0',-100],['100',0],['90',-10],['110',10]]){
    const parsed=parseCountedCash(input);
    const countedCash=parsed.error?null:Number(parsed.value);
    assert.equal(runInNewContext(expression,{countedCash,expectedCash:100,hasActiveShift:true}),expected);
  }
});

function closeFixture(input,fail=false){
  const state={calls:[],error:'',closed:false,cleared:false,success:''};
  const parseOpeningFund=actual('function parseOpeningFund','\n\nfunction');
  const context={selectedWarehouseId:'A',warehouseContextReady:true,hasActiveShift:true,closeShiftForm:{efectivo_contado:input,notas:'Synthetic'},token:'fixture',empresaId:'T',
    defaultCloseShiftForm:{efectivo_contado:'',notas:''},cashActionRef:{current:''},
    setError:v=>{state.error=v;},setCloseShiftError:v=>{state.error=v;},setShiftSubmitting(){},
    startCashAction:()=>true,finishCashAction(){},clearFeedback:()=>{state.success='';},
    closePosShift:async request=>{state.calls.push(request);if(fail)throw new Error('Internal Server Error');return{id:'SHIFT'};},
    setActiveShift(){},setCloseShiftForm:()=>{state.cleared=true;},setCloseShiftModalOpen:v=>{state.closed=!v;},
    refreshPosData:async()=>{},setSuccess:v=>{state.success=v;},setSuccessContext(){},
    getPosUiError:(e,f)=>e.message||f,
  };
  context.parseCountedCash=actual('function parseCountedCash','\n\nfunction',{parseOpeningFund});
  if(source.includes('function getCashOperationError'))context.getCashOperationError=actual('function getCashOperationError','\n\nfunction',context);
  return{state,submit:actual('async function handleCloseShiftSubmit','\n  async function handleCancelSale',context)};
}

test('F06 invalid/blank counts block close; zero valid; failure preserves captured form',async()=>{
  for(const input of['','-1','invalid']){const{state,submit}=closeFixture(input);await submit({preventDefault(){}});
    assert.equal(state.calls.length,0);assert.equal(state.cleared,false);assert.ok(state.error);}
  const zero=closeFixture('0');await zero.submit({preventDefault(){}});assert.equal(zero.state.calls[0].payload.efectivo_contado,'0');
  const failed=closeFixture('90',true);await failed.submit({preventDefault(){}});
  assert.equal(failed.state.closed,false);assert.equal(failed.state.cleared,false);assert.equal(failed.state.success,'');
  assert.ok(!failed.state.error.includes('Internal Server Error'));
});

test('F07 per-action progress has exact copy and a shared disable flag never labels ticket/suspend as charge',()=>{
  const label=actual('function getSaleActionLabel','\n\nfunction');
  assert.equal(label('charge'),'Cobrando...');assert.equal(label('suspend'),'Suspendiendo...');assert.equal(label('ticket'),'Abriendo ticket...');
  const cash=actual('function getCashActionLabel','\n\nfunction');assert.equal(cash('income'),'Guardando ingreso...');
  assert.ok(!source.includes('submitting ? "Cobrando..."'));
  assert.ok(source.includes('saleAction === "charge"'));
});

test('F07 each actual handler starts and finishes its own action',async()=>{
  for(const[name,end,expected]of[['async function openTicket','\n  async function loadInvoiceCrmSuggestion','ticket'],
    ['async function openSaleDetail','\n  async function openTicket','detail']]){
    const wait=deferred(),actions=[];
    const context={startSaleAction:action=>{actions.push(action);return true;},finishSaleAction:action=>actions.push('done:'+action),
      setSubmitting(){},clearFeedback(){},loadSaleArtifacts:()=>wait.promise,setShiftReportModalOpen(){},setTicketModalOpen(){},setDetailModalOpen(){},
      setError(){},getPosUiError:(e,f)=>f};
    const operation=actual(name,end,context);const pending=operation(expected==='detail'?{id:'S'}:'S');
    assert.equal(actions[0],expected);wait.resolve();await pending;assert.equal(actions.at(-1),'done:'+expected);
  }
});

test('F07 manual cash local and structured 422 errors map only to Spanish amount/reason fields',()=>{
  const validate=actual('function getManualCashFieldErrors','\n\nfunction');
  const local=validate({monto:'',motivo:''});assert.ok(local.monto);assert.ok(local.motivo);
  const backend=validate({monto:'1',motivo:'Synthetic'},{status:422,detail:[{loc:['body','monto'],msg:'Input should be a valid decimal'}]});
  assert.ok(backend.monto);assert.ok(!backend.monto.includes('Input should'));assert.equal(backend.motivo,undefined);
});

test('F07 search empty distinguishes applied search from unfiltered empty catalogue',()=>{
  const empty=actual('function getCatalogEmptyState','\n\nfunction');
  assert.equal(empty({status:'ready',query:'no-match'}).title,'Sin coincidencias');
  assert.equal(empty({status:'ready',query:''}).title,'No hay productos disponibles');
  assert.equal(empty({status:'loading',query:''}).title,'Cargando catálogo');
  assert.ok(source.includes('Limpiar búsqueda'));
});

test('F07 discount labels clarify unit and tax shows the equivalent percentage',()=>{
  const tax=actual('function getTaxRateHelp','\n\nfunction');
  assert.equal(tax('0.16'),'0.16 = 16%');
  assert.ok(source.includes('Descuento por unidad'));
});

test('F07 resumed sale renders exactly one editable global discount control',()=>{
  const tree=parser.parse(source,{sourceType:'module',plugins:['jsx']});
  function count(resumed){let inputs=0;
    function walk(node){if(!node||typeof node!=='object')return;
      if(node.type==='ConditionalExpression'&&node.test.type==='Identifier'&&node.test.name==='isEditingSuspendedSale'){
        walk(resumed?node.consequent:node.alternate);return;}
      if(node.type==='JSXOpeningElement'&&node.name.name==='input'){
        const value=node.attributes.find(a=>a.name?.name==='value')?.value?.expression;
        if(value?.name==='editableDiscountGlobalInput'||(value?.object?.name==='saleForm'&&value?.property?.name==='descuento_global'))inputs++;
      }
      for(const value of Object.values(node)){if(Array.isArray(value))value.forEach(walk);else if(value&&typeof value==='object')walk(value);}}
    walk(tree);return inputs;}
  assert.equal(count(true),1);assert.equal(count(false),1);
});

test('F06 valid counted input still leaves difference pending if expected shift is unavailable',()=>{
  const expression=source.match(/const closeShiftDifference = (.*);/)[1];
  assert.equal(runInNewContext(expression,{countedCash:90,expectedCash:0,hasActiveShift:false}),null);
});

function manualFixture(form, failure=null, wait=null){
  const state={requests:[],error:'',fields:{},cleared:false,open:'ingreso',action:'',success:''};
  const context={selectedWarehouseId:'A',shiftMovementForm:form,shiftMovementModalType:'ingreso',activeShift:{almacen_id:'A',efectivo_esperado:100},
    token:'fixture',empresaId:'T',defaultShiftMovementForm:{monto:'',motivo:''},shiftHistoryFilters:{},
    setShiftMovementError:value=>{state.error=value;},setShiftMovementFieldErrors:value=>{state.fields=value;},
    startCashAction:action=>{state.action=action;return true;},finishCashAction:()=>{state.action='';},
    clearFeedback:()=>{state.success='';},setActiveShift(){},setShiftMovementForm:()=>{state.cleared=true;},
    setShiftMovementModalType:value=>{state.open=value;},loadShiftHistory:async()=>{},setSuccess:value=>{state.success=value;},
    getPosUiError:(e,f)=>e.message||f,
    createPosShiftManualIncome:async request=>{state.requests.push(request);if(wait)await wait.promise;if(failure)throw failure;return{};},
  };
  context.getManualCashFieldErrors=actual('function getManualCashFieldErrors','\n\nfunction');
  context.getCashOperationError=actual('function getCashOperationError','\n\nfunction',context);
  return{state,submit:actual('async function handleShiftMovementSubmit','\n  function openCloseShiftModal',context)};
}

test('F07 empty income blocks API with field errors; slow valid income has specific action',async()=>{
  const blank=manualFixture({monto:'',motivo:''});await blank.submit({preventDefault(){}});
  assert.equal(blank.state.requests.length,0);assert.ok(blank.state.fields.monto);assert.ok(blank.state.fields.motivo);
  assert.equal(blank.state.cleared,false);assert.equal(blank.state.success,'');
  const wait=deferred();const valid=manualFixture({monto:'10',motivo:'Synthetic'},null,wait);
  const pending=valid.submit({preventDefault(){}});assert.equal(valid.state.action,'income');
  wait.resolve();await pending;assert.equal(valid.state.action,'');assert.equal(valid.state.open,'');
});

test('F07 structured income rejection remains localized and preserves entered values',async()=>{
  const form={monto:'10',motivo:'Synthetic'};
  const failure={status:422,message:'Input should be a valid decimal',detail:[{loc:['body','monto'],msg:'Input should be a valid decimal'}]};
  const {state,submit}=manualFixture(form,failure);await submit({preventDefault(){}});
  assert.equal(state.cleared,false);assert.equal(state.open,'ingreso');assert.equal(form.monto,'10');assert.equal(form.motivo,'Synthetic');
  assert.ok(state.fields.monto);assert.equal(state.fields.motivo,undefined);assert.ok(!state.error.includes('Input should'));
});

test('F07 closing/reopening cash modal clears general and field errors',()=>{
  const state={error:'Old',fields:{monto:'Old'},open:'ingreso'};
  const context={cashActionRef:{current:''},setShiftMovementError:v=>{state.error=v;},
    setShiftMovementFieldErrors:v=>{state.fields=v;},setShiftMovementModalType:v=>{state.open=v;}};
  actual('function closeShiftMovementModal','\n  async function handleShiftMovementSubmit',context)();
  actual('function openShiftMovementModal','\n  function closeShiftMovementModal',context)('ingreso');
  assert.equal(state.error,'');assert.equal(Object.keys(state.fields).length,0);assert.equal(state.open,'ingreso');
});

test('F07 action tracker does not clear or relabel an operation still in flight',()=>{
  const state={action:''};const context={saleActionRef:{current:''},setSaleAction:v=>{state.action=v;}};
  const start=actual('function startSaleAction','\n  function finishSaleAction',context);
  const finish=actual('function finishSaleAction','\n  function startCashAction',context);
  assert.equal(start('ticket'),true);assert.equal(start('charge'),false);finish('charge');
  assert.equal(state.action,'ticket');finish('ticket');assert.equal(state.action,'');
});

test('F07 clearing search reloads unfiltered catalogue instead of creating materials',async()=>{
  let filters,request;
  const context={catalogFilters:{q:'missing',offset:25},selectedWarehouseId:'A',catalogSearchActionRef:{current:0},
    setCatalogFilters:v=>{filters=v;},clearFeedback(){},setCatalogSearching(){},setError(){},
    loadCatalog:async(id,value)=>{request={id,value};}};
  await actual('async function handleClearCatalogSearch','\n  async function handleCatalogScan',context)();
  assert.equal(filters.q,'');assert.equal(filters.offset,0);assert.equal(request.id,'A');assert.equal(request.value.q,'');
});

test('F07 valid charge/suspend handlers keep their actual action throughout a slow request',async()=>{
  for(const action of ['charge','suspend']){
    const wait=deferred(),events=[];
    const context={warehouseContextReady:true,pendingWarehouseId:'',warehouseChangeSubmitting:false,selectedWarehouseId:'A',
      selectedWarehouse:{id:'A'},hasActiveShift:true,hasCartItems:true,cartHasInvalidQuantity:false,cartHasInvalidDiscount:false,
      cartHasMissingManualDescription:false,cartHasMissingPrice:false,usesMixedPayments:false,paymentRows:[],nonCashOverageWithoutCash:false,
      paidPreview:10,cartTotal:10,token:'fixture',empresaId:'T',resumedSaleId:'',saleFilters:{},
      saleForm:{cliente_nombre:'',cliente_email:'',metodo_pago:'efectivo',monto_recibido:'10',descuento_global:'',notas:''},
      cart:[{tipo_linea:'material',material_id:'M',cantidad:'1',precio_unitario:'10',descuento_unitario:'0',impuesto_tasa:'0'}],
      isInventoryTrackedLine:()=>true,getSaleLineDisplayName:()=>'',startSaleAction:value=>{events.push(value);return true;},
      finishSaleAction:value=>events.push('done:'+value),setError(){},setWarehouseChangeError(){},clearFeedback(){},
      createPosSale:async()=>{await wait.promise;return{id:'S'};},suspendPosSale:async()=>{await wait.promise;return{id:'S'};},
      loadSaleArtifacts:async()=>{},clearCart(){},setResumedSaleId(){},refreshPosData:async()=>{},
      setSuccess(){},setSuccessContext(){},setTicketModalOpen(){},updateView(){},getPosUiError:(e,f)=>f};
    const operation=action==='charge'?actual('async function handleCreateSale','\n  async function handleOpenShift',context)
      :actual('async function handleSuspendSale','\n  async function handleResumeSale',context);
    const pending=action==='charge'?operation({preventDefault(){}}):operation();
    assert.equal(events[0],action);assert.equal(events.length,1);wait.resolve();await pending;
    assert.equal(events.at(-1),'done:'+action);
  }
});

test('F07 unexpected server errors are neutral without exposing raw technical details',()=>{
  const error=actual('function getCashOperationError','\n\nfunction',{getPosUiError:e=>e.message});
  assert.equal(error({status:500,message:'Unexpected driver failure'},'No se pudo guardar.'),'No se pudo guardar.');
  assert.equal(error({message:'[object Object]'},'No se pudo guardar.'),'No se pudo guardar.');
  assert.equal(error({status:409,message:'El retiro supera el efectivo disponible.'},'Error'),'El retiro supera el efectivo disponible.');
});

test('F06 typing invalid counted cash shows localized error even when submit is disabled',()=>{
  const tree=parser.parse(source,{sourceType:'module',plugins:['jsx']});let change;
  function walk(node){if(!node||typeof node!=='object')return;
    if(node.type==='JSXOpeningElement'&&node.name.name==='input'){
      const value=node.attributes.find(a=>a.name?.name==='value')?.value?.expression;
      if(value?.object?.name==='closeShiftForm'&&value?.property?.name==='efectivo_contado')change=node.attributes.find(a=>a.name?.name==='onChange').value.expression;
    }
    for(const item of Object.values(node)){if(Array.isArray(item))item.forEach(walk);else if(item&&typeof item==='object')walk(item);}}
  walk(tree);
  let form={efectivo_contado:'',notas:''},error='';
  const parseOpeningFund=actual('function parseOpeningFund','\n\nfunction');
  const parseCountedCash=actual('function parseCountedCash','\n\nfunction',{parseOpeningFund});
  const handler=runInNewContext(`(${source.slice(change.start,change.end)})`,{parseCountedCash,
    setCloseShiftForm:update=>{form=update(form);},setCloseShiftError:value=>{error=value;}});
  handler({target:{value:'-1'}});assert.equal(form.efectivo_contado,'-1');assert.ok(error);
  handler({target:{value:'invalid'}});assert.equal(form.efectivo_contado,'invalid');assert.ok(error);
  handler({target:{value:'90'}});assert.equal(error,'');
});
