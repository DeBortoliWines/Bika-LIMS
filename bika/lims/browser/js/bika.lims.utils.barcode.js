// This function will redirect based on a barcode sequence.
//
// The string is sent to python, who will return a URL, which
// we will use to set the window location.
//
// A barcode may begin and end with '*' but we can't make this
// assumption about all scanners; so, we will function with a
// 500ms timeout instead.

$(document).ready(function(){

    function barcode_listener() {

        var that = this;

        that.load = function() {

            // if collection gets something worth submitting,
            // it's sent to utils.barcode_entry here.
            function redirect(code){
                authenticator = $('input[name="_authenticator"]').val();
                $.ajax({
                    type: 'POST',
                    url: 'barcode_entry',
                    data: {
                        'entry':code,
                        '_authenticator': authenticator},
                    success: function(responseText, statusText, xhr, $form) {
                        if (responseText.success) {
                            window.location.href = responseText.url;
                        }
                    }
                });
            }

            var collecting = false;
            var code = ""

            $(window).keypress(function(event) {
                if (collecting) {
                    code = code + String.fromCharCode(event.which);
                } else {
                    collecting = true;
                    code = String.fromCharCode(event.which);
                    setTimeout(function(){
                        collecting = false;
                        if (code.length > 2){
                            redirect(code);
                        }
                    }, 500)
                }
            });
        }
    }

    // immediately load the barcode_listener so that barcode entries are detected
    // in all windows (when there is no input element selected).
    window.bika = window.bika || { lims: {} };
    window.bika.lims['barcode_listener'] = new barcode_listener();
    window.bika.lims['barcode_listener'].load();

});

