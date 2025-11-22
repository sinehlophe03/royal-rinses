async function fetchSlots(){
  const dateInput = document.getElementById('date-input');
  const timeSelect = document.getElementById('time-select');
  if(!dateInput) return;
  const date = dateInput.value;
  timeSelect.innerHTML = '<option>Loading...</option>';
  try{
    const resp = await fetch(`/api/slots?date=${date}`);
    const j = await resp.json();
    if(j.slots && j.slots.length){
      timeSelect.innerHTML = '';
      j.slots.forEach(s=>{
        const opt = document.createElement('option'); opt.value = s; opt.textContent = s; timeSelect.appendChild(opt);
      });
    } else {
      timeSelect.innerHTML = '<option value="">No slots available</option>';
    }
  }catch(e){
    timeSelect.innerHTML = '<option value="">Error loading</option>';
  }
}

document.addEventListener('change', (e)=>{
  if(e.target && e.target.id==='date-input') fetchSlots();
});
