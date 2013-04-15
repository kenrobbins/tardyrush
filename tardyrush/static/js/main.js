function update_csrf(data) {
    if (data.csrf_token) {
        $('input[name=csrf_token]').val(data.csrf_token);
    }
}

function update_player_status(match_id, new_status) {
    var form = $('#sb_form_'+match_id);
    var csrf = form.find('input[name=csrf_token]').val();
    var url = form.attr('action');
    $.post(url, {
            csrf_token: csrf,
            s: new_status,
            api: '1'
        }, function(data) {
            update_csrf(data);
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

                var newrow = "<tr class='info'><td>" + data.user_name +
                              "</td><td id='"+id+"' class='"+lower_status+"'>"+
                              data.player_status_pretty+"</td></tr>";

                if (before) {
                    before.before(newrow);
                }
                else {
                    tbl.append(newrow);
                }
                tbl.show();

                var sb = $('#status_buttons_'+data.match_id+' li');
                sb.each(function(index, value) {
                    var btn = $(value);
                    if (btn.hasClass(lower_status)) {
                        btn.hide();
                    } else {
                        btn.show();
                    }
                });
            }
            else {
                alert("An error has occured. Please try again.");
            }
        }, 'json');
    return false;
}

function save_form(type) {
    var form = $('#'+type+'_form');
    var modal = $('#'+type+'_modal');
    var csrf = form.find('input[name=csrf_token]').val();

    data = {
        csrf_token: csrf,
        api: '1'
    };

    var update_type = 'added';
    var type_pretty = null;
    if (type == 'opponent') {
        type_pretty = 'Opponent';
        data.name = form.find('input[name=name]').val();
        data.tag = form.find('input[name=tag]').val();
    }
    else if (type == 'server') {
        type_pretty = 'Server';
        data.name = form.find('input[name=name]').val();
        data.address = form.find('input[name=address]').val();
    }
    else { // time_zone
        type_pretty = 'Time zone';
        update_type = 'changed';
        data.time_zone = form.find('select[name=time_zone]').val();
    }

    var url = form.attr('action');

    $.post(url, data, function(data) {
            update_csrf(data);
            form.find('.help-inline').remove();
            form.find('.error').removeClass("error");
            modal.find('.modal_alert').remove();
            if (data.success) {
                if (type == 'time_zone') {
                    label = 'Date (in ' + data.user_tz_names[0] + ')';
                    $("#match_form label[for=date]").html(label);
                }
                else {
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
                }

                modal.modal('hide');

                form.find('input[type=text]').val('');

                var flash = '<div class="modal_alert alert alert-success">';
                flash += '<button type="button" class="close" data-dismiss="alert">&times;</button>';
                flash += '<strong>Hooray!</strong> '+type_pretty+' '+update_type+' successfully.';
                flash += '</div>';

                $('#match_form').before(flash);
            }
            else {
                var flash = '<div class="modal_alert alert alert-error">';
                flash += '<button type="button" class="close" data-dismiss="alert">&times;</button>';
                flash += '<strong>Uh oh!</strong> Something went wrong.';
                flash += '</div>';
                form.before(flash);
                $.each(data.errors, function(key, val) {
                    var input = form.find('input[name='+key+']');
                    var span_check = input.next();

                    input.parent().parent().addClass("error");

                    if (span_check.attr('class') == 'help-inline') {
                        span_check.html(val);
                    }
                    else {
                        var err = "<span class='help-inline'>"+val+"</span>";
                        input.after(err);
                    }
                });
            }
        }, 'json');
    return false;
}
