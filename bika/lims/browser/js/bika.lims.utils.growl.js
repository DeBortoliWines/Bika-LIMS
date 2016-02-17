/**
 * Utility script for Growl style notifications using Plone messaging
 * 
 * This script will check for any Plone notification messages (class portalMessage) and render them
 * as Growl style notifications instead, with error messages being fixed till
 * dismissed and info messages being auto-dismissed. 
 * 
 * TODO All notification styles, only error done for now
 */

$(document).ready(function(){

	// iterate all error portal messages
	$('.portalMessage.error dd').each(function (idx) {
		//$(this).parent().hide(); // don't need to hide anymore, hidden by default by CSS
		var $msg = $(this).html();

		$.growl.error({message: $msg, fixed: true, location: 'tc'});
	});

});