(function(){
	// UNUSED! Period is disallowed regardless now
  function checkUsername(u){
	return (
      /^\./.test(u)? 'You cannot start username with a period.':
	  /\.$/.test(u)? 'You cannot end username with a period.':
	  /\.\./.test(u)? 'You cannot have more than one period in a row.':
	  u.match(/\.(com|net|org|txt)$/)? 'Your username cannot end with .' + forbidden_extensions[1]:
		'ok'
	);
  }


  function attachUsernameInput(){
	const usernameInputs = document.getElementsByClassName('username-input');
	for(var i=0;i<usernameInputs.length;i++)(function(usernameInput){
      let lastValue = '';
	  const endpoint = usernameInput.getAttribute('data-endpoint');
      let usernameInputMessage = document.createElement('small');
      usernameInput.oninput = function(event){
		let value = usernameInput.value;
		if (value != lastValue){
          if(!/^[a-z0-9_ ]*$/i.test(value)){
			usernameInputMessage.innerHTML = 'Usernames can only contain letters, numbers, and underscores.';
			usernameInputMessage.className = 'username-input-message error';
			event.preventDefault();
			return;
          }
          if(/ /.test(value)){
			value = value.replace(/ /g,'_');
          }
          usernameInput.value = lastValue = value.toLowerCase();
          if(!value){
			usernameInputMessage.innerHTML = 'You cannot have an empty username.';
			usernameInputMessage.className = 'username-input-message error';
			return;
          }
          if(/^[01]/.test(value)) {
			usernameInputMessage.innerHTML = 'Your username cannot start with 0 or 1.';
			usernameInputMessage.className = 'username-input-message error';
			return;
		  }
          usernameInputMessage.innerHTML = 'Checking username...';
          usernameInputMessage.className = 'username-input-message checking';
          requestUsernameAvailability(value, endpoint).then((resp) => {
			if (['ok', void 0].indexOf(resp.status) < 0){
              usernameInputMessage.innerHTML = 'Sorry, there was an unknown error.';
              usernameInputMessage.className = 'username-input-message error';
              return;
			}
			if (resp.is_available){
              usernameInputMessage.innerHTML = "The username @" + value + " is available!";
              usernameInputMessage.className = 'username-input-message success';
              return;
			} else {
              usernameInputMessage.innerHTML = "Sorry, someone else has this username already :(";
              usernameInputMessage.className = 'username-input-message error';
              return;
			}
          });
		}
      };
      usernameInputMessage.className = 'username-input-message';
      usernameInput.parentNode.appendChild(usernameInputMessage);
	})(usernameInputs[i]);
  }

  async function requestUsernameAvailability(u, endpoint){
	return fetch(endpoint.replace('$1', encodeURIComponent(u))
		).then((e) => e.json());
  }

  function enablePostVotes(){
	for (let elem of document.querySelectorAll('.upvote-button')){
	  (function(e){
		let p;
		for (p = e; p && p != document.body && !p.hasAttribute('data-endpoint'); p = p.parentElement);

		if (!p) return;

		let endpoint = p.getAttribute('data-endpoint');
		

		if (!endpoint || !/^[a-z0-9_]+$/.test(endpoint)) {
			console.warn('missing endpoint!');
			return;
		}
	  

		let buttonUp = e.querySelector('.upvote-button-up'), buttonDown = e.querySelector('.upvote-button-down'), 
			upvoteCount = e.querySelector('.upvote-count');
		let currentScore = buttonUp.classList.contains('active')? 1 : buttonDown.classList.contains('active')? -1 : 0;

		buttonUp.addEventListener('click', function(){
		  sendVote(endpoint, (currentScore === 1? 0 : 1)).then((e) => {
				buttonDown.classList.remove('active');
				buttonDown.querySelector('i').className = 'icon icon-downvote';
				if(currentScore === 1) {
					buttonUp.classList.remove('active');
					buttonUp.querySelector('i').className = 'icon icon-upvote';
				} else {
					buttonUp.classList.add('active');
					buttonUp.querySelector('i').className = 'icon icon-upvote_fill';
				}
				upvoteCount.textContent = e.count !== void 0? e.count : upvoteCount.textContent;
				currentScore = currentScore === 1? 0 : 1;
		    });
		});

		buttonDown.addEventListener('click', function(){
			sendVote(endpoint, (currentScore === -1? 0 : -1)).then((e) => {
				buttonUp.classList.remove('active');
				buttonUp.querySelector('i').className = 'icon icon-upvote';
				if(currentScore === -1) {
					buttonDown.classList.remove('active');
					buttonDown.querySelector('i').className = 'icon icon-downvote';
				} else {
					buttonDown.classList.add('active');
					buttonDown.querySelector('i').className = 'icon icon-downvote_fill';
				}
				upvoteCount.textContent = e.count !== void 0? e.count : upvoteCount.textContent;
				currentScore = currentScore === -1? 0 : -1;
		    });
		});
	  })(elem);
	}
  }

  function getCsrfToken(){
	return document.querySelector('meta[name="csrf_token"]').content;
  }

  async function sendVote(endpoint, score){
	return fetch(`/comments/${endpoint}/upvote`, {
	  method: 'POST',
	  headers: {
		'Content-Type': 'application/x-www-form-urlencoded'
	  },
	  body: 'o=' + encodeURIComponent(score) + '&csrf_token=' + encodeURIComponent(getCsrfToken())
	}).then(e => e.json());
  }

  function main() {
	attachUsernameInput();
	enablePostVotes();
  }

  main();
  
})();
