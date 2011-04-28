function update_player_status(obj) {
    var form = $(obj).parent();
    var csrf = form.find('input[name=csrf]').val();
    var s = form.find('input[name=s]').val();
    var url = form.attr('action');
    $.post(url, {
            csrf: csrf,
            s: s,
            api: '1'
        }, function(data) {
            if (data.success) {
                var lower_status = data.player_status_pretty.toLowerCase();
                var id = 'status_' + data.match_id + '_' + data.user_id;

                var idel = $("#"+id);
                idel.parent().remove();

                var tbl = $('#match_'+data.match_id);

                var firstmaybe = null;
                var firstunavail = null;

                tbl.find('tr').each(function() {
                    var stat = $(this).find('td').last().html();
                    if (stat) {
                        var statlower = $.trim(stat.toLowerCase());
                        if (!firstmaybe && statlower == 'maybe')
                            firstmaybe = $(this);
                        
                        if (!firstunavail && statlower == 'unavailable')
                            firstunavail = $(this);
                    }
                });

                var before = null;
                if (lower_status == 'available') {
                    if (firstmaybe)
                        before = firstmaybe;
                    else if (firstunavail)
                        before = firstunavail;
                }
                else if (lower_status == 'maybe') {
                    if (firstunavail)
                        before = firstunavail;
                }

                var newrow = "<tr class='current_user'><td>" + data.user_name + 
                              "</td><td id='"+id+"' class='"+lower_status+"'>"+
                              data.player_status_pretty+"</td></tr>";

                if (before) {
                    before.before(newrow);
                }
                else {
                    tbl.append(newrow);
                }
                tbl.show();

                var btnid = '#sb_'+lower_status+'_'+data.match_id;
                $('#status_buttons_'+data.match_id).find('form').show();
                $(btnid).hide();
            }
            else {
                alert("An error has occured. Please try again.");
            }
        }, 'json');
    return false;
}

function save_form(type) {
    var type_pretty = type == 'opponent' ? 'Opponent' : 'Server';
    var form = $('#'+type+'_form');
    var csrf = form.find('input[name=csrf]').val();
    var name = form.find('input[name=name]').val();

    data = {
        csrf: csrf,
        name: name,
        api: '1'
    };

    if (type == 'opponent') {
        data.tag = form.find('input[name=tag]').val();
    }
    else {
        data.address = form.find('input[name=address]').val();
    }

    var url = form.attr('action');

    $.post(url, data, function(data) {
            form.find('.errors').remove();
            if (data.success) {
                var newval = $("<option></option>").
                    attr("value", data[type+'_id']).
                    text(data[type+'_name']);
                var sel = $('select#'+type+'_id');
                var opts = sel.children("option");
                var oname = data[type+'_name'].toLowerCase();
                var added = false;
                for (var i = 0; i < opts.length; ++i) {
                    var o = $.trim($(opts[i]).html().toLowerCase());
                    if (o > oname) {
                        $(opts[i]).before(newval);
                        added = true;
                        break;
                    }
                }
                if (!added)
                    sel.append(newval);
                sel.val(data[type+'_id']);

                $.fancybox.close();

                form.find('input[type=text]').val('');

                $('#match_form').before(
                    '<p id="addflash">'+type_pretty+' added successfully.</p>');
                $('#addflash').fadeIn(2500).delay(2000).fadeOut(2500);

                (function (el) {
                    setTimeout(function() {
                        el.remove();
                    }, 5000);
                } ($('#addflash')));
            }
            else {
                $.each(data.errors, function(key, val) {
                    var err = "<ul class='errors'><li>"+val+"</li></ul>";
                    form.find('input[name='+key+']').before(err);
                });
            }
        }, 'json');
    return false;
}

