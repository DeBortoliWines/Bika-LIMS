jQuery( function($) {
$(document).ready(function(){

	// Hide remarks field if this object is in portal_factory
	if(window.location.href.search("portal_factory") > -1) {
		$("#archetypes-fieldname-Remarks").toggle(false);
	}

	$('.saveRemarks').live('click', function(event){
		event.preventDefault();
		if ($("#Remarks").val() == '' ||
		    $("#Remarks").val() == undefined) {
			return false;
		}

		$("#archetypes-fieldname-Remarks fieldset span").load(
			$('#setRemarksURL').val() + "/setRemarksField",
			{'value': $("#Remarks").val(),
			 '_authenticator': $('input[name="_authenticator"]').val()}
		);
		$("#Remarks").val("");
		return false;
	});
	$("#Remarks").empty();
	$("#archetypes-fieldname-Remarks fieldset span").load(
		$('#setRemarksURL').val() + "/getRemarksField",
		{'_authenticator': $('input[name="_authenticator"]').val()}
	);

	if($("#archetypes-fieldname-Remarks fieldset span").length == 0) {
		// remarks not being rendered, assumes closed workflow
		$(".viewRemarks").before("<fieldset style='margin-top:2em;'><legend>History</legend></fieldset>");
		$(".viewRemarks").css('margin-top', '');
		$(".viewRemarks").load(
			$('#setRemarksURL').val() + "/getRemarksField",
			{'_authenticator': $('input[name="_authenticator"]').val()}
		);
	}
});
});


