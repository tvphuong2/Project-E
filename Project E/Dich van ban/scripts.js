var S_ENG = ""
var S_VI = ""
var eng = []
var vi = []
var eye = false
var left = false
var fail = 0

$('#myModal').modal('show');

function splitLine(s) {
    return s.replaceAll(/<\/?[^>]+(>|$)/g, "").replaceAll("&nbsp;", " ").replaceAll("...", "").replaceAll(/  +/g, ' ').replace(/\s+$/, '').split(/[.!?]+/)
}

function splitStr(ss) {
    sss = ss.split(" ")
    var out = []
    for (let j = 0; j < sss.length; j++) {
        if (sss[j]) {
            out.push(sss[j])
        }
    }
    return out
}

function buildVi(eng, vi) {
    let code = ""
    for (let i = 0; i < vi.length; i++) {
        code += '<div>' + vi[i] + '</div>'
    }
    $("#topic").html(code)
    $(document).ready(function(){
        $('[data-toggle="tooltip"]').tooltip();   
    });
}

function buildEng(eng) {
    let code = ""
    let dif = $("#difficulty").val()
    console.log(dif)
    for (let i = 0; i < eng.length; i++) {
        code += "<div>"
        code += '<div class = "vietnamese2">'+vi[i]+'</div>'
        code += '<span role="textbox" class="block" id ="b'+i+'" contenteditable></span>'
        code += '<i class = "block_ans">'+eng[i]+'</i>'
        code += "</div>"
    }
    $("#ans").html(code)
}

function build() {
    S_ENG = $("#end_input").html()
    S_VI = $("#vi_input").html()
    eng = splitLine(S_ENG)
    vi = splitLine(S_VI)
    
    buildVi(eng, vi)
    buildEng(eng)

    let left = document.getElementById("topic")
    let right = document.getElementById("ans")
    setID(left.childNodes, right.childNodes)
}

function check() {
    fail = 0
    for (i = 0; i < eng.length; i++) {
        let ll = eng[i].replaceAll(/<\/?[^>]+(>|$)/g, "").replaceAll("&nbsp;", " ").replaceAll("...", "").replaceAll(/  +/g, ' ').replace(/\s+$/, '').split(" ")
        let r = $("#b" + i).html()
        let rr = r.replaceAll(/<\/?[^>]+(>|$)/g, "").replaceAll("&nbsp;", " ").replaceAll("...", "").replaceAll(/  +/g, ' ').replace(/\s+$/, '').split(" ")

        rr = seqMode(rr, ll)

        let new_str = ""
        for (let j = 0; j < rr.length; j++) {
            new_str += rr[j] + " "
        }
        $("#b" + i).html(new_str)
    }
    $("#error").html(fail)
    let score = document.getElementById("score");
}

function showAns() {
    console.log("pip")
    eye = !eye
    if (eye) {
        $("#eye").html('<span class="glyphicon glyphicon-eye-open"></span>')
        $(".block_ans").css("display", "inline-block")
    } else {
        $("#eye").html('<span class="glyphicon glyphicon-eye-close"></span>')
        $(".block_ans").css("display", "none")
    }
}

function goLeft() {
    left = !left
    if (left) {
        $("#ngang").css("grid-template-columns", "8% 92%")
        $("#scripts").css("display", "none")
        $("#left").html('<span class="glyphicon glyphicon-triangle-right"></span>')
        $(".vietnamese2").css("display", "inline-block")
    } else {
        $("#ngang").css("grid-template-columns", "48% 4% 48%")
        $("#scripts").css("display", "block")
        $("#left").html('<span class="glyphicon glyphicon-triangle-left"></span>')
        $(".vietnamese2").css("display", "none")
    }
}

function setID(l, r) {
    for (let i = 0; i < l.length; i++) {
        l[i].setAttribute("id", "l" + i)
    }
    for (let i = 0; i < r.length; i++) {
        r[i].setAttribute("id", "r" + i)
        $('#r' + i).hover(function() {
            tg = "#" + this.id.replaceAll("r", "l")
            $(tg).css('background-color', ' rgb(233, 233, 233)');
          }, function() {
            tg = "#" + this.id.replaceAll("r", "l")
            $(tg).css('background-color', '');
          });
    }
}

var wage = document.getElementById("body");
wage.addEventListener("keydown", function (e) {
    if (e.code === "ArrowUp") {
        check()
    }
});

function seqMode(rr, ll) {
    let l_index = 0
    let f = false
    
    for (let j = 0; j < rr.length; j++) {
        let r_stand = rr[j].replaceAll(",", "").replaceAll(".", "").replaceAll(" ", "").replaceAll("’", "'").toLowerCase()
        for (z = l_index; z < ll.length; z++) {
            let l_stand = ll[z].replaceAll(",", "").replaceAll(".", "").replaceAll(" ", "").replaceAll("’", "'").toLowerCase()
            if (r_stand == l_stand) {
                l_index = z + 1
                f = false
                break
            } else {
                if (!f) {
                    f = true
                    rr[j] = "... " + rr[j]
                    fail+= 1
                }
            }
            if (z == ll.length - 1) {
                rr[j] = "<b>" + rr[j].replaceAll("... ", "") + "</b>"
                fail+= 1
            }
        }
    }
    return rr
}


// var mode = 0
// var fail = 0

// function handleFiles(event) {
//     var files = event.target.files;
//     $("#src").attr("src", URL.createObjectURL(files[0]));
//     document.getElementById("audio").load();
// }

// var wage = document.getElementById("body");
// wage.addEventListener("keydown", function (e) {
//     if (e.code === "MediaTrackPrevious") {  //checks whether the pressed key is "Enter"
//         let aud = document.getElementById("audio")
//         let val = document.getElementById("previous")
//         aud.currentTime -= val.value
//     }
//     if (e.code === "MediaPlayPause") {  //checks whether the pressed key is "Enter"
//         let aud = document.getElementById("audio")
//         let val = document.getElementById("pause")
//         aud.currentTime -= val.value
//     }
//     if (e.code === "MediaTrackNext") {  //checks whether the pressed key is "Enter"
//         check()
//     }
// });

// document.getElementById("upload").addEventListener("change", handleFiles, false);
// document.getElementById("load_save").addEventListener("change", load, false);


// function start() {
//     let ngang = document.getElementById("ngang");
//     let but = document.getElementById("start");
//     let scrips = document.getElementById("scripts");
//     if (mode == 0) {
//         ngang.style.gridTemplateColumns = "4% 96%";
//         scrips.style.display = "none"
//         but.innerHTML = "?"
//         mode = 1
//     }
//     else {
//         ngang.style.gridTemplateColumns = "48% 4% 48%";
//         scrips.style.display = "block"
//         but.innerHTML = "◄"
//         mode = 0
//         check()
//     }
// }

// function removeName() {
//     let topic = document.getElementById("topic");
//     let search = document.getElementById("search");
//     var scripts = topic.innerHTML
//     topic.innerHTML = scripts.replaceAll(search.value, "")
// }

// function removeSpace() {
//     let topic = document.getElementById("topic");
//     var scripts = topic.childNodes
//     for (let i = 0; i < scripts.length; i++) {
//         let s = scripts[i].innerHTML
//         s = s.replace(/<[^>]*>?/gm, '')
//         if (s == "") {
//             topic.removeChild(topic.children[i])
//             i--
//         } else {
//             scripts[i].innerHTML = s
//         }
//     }
// }

// function splitLine() {
//     let left = document.getElementById("topic");
//     l = left.innerHTML.replaceAll(/<\/?[^>]+(>|$)/g, "").replaceAll("&nbsp;", " ").replaceAll("...", "").replaceAll(/  +/g, ' ').replace(/\s+$/, '').split(/[.!?]+/)
//     let out = ""
//     for (let i = 0; i < l.length; i++) {
//         out += "<div>" + l[i] + "</div>"
//     }
//     left.innerHTML = out
// }

// function check() {
//     let left = document.getElementById("topic");
//     let right = document.getElementById("ans");
//     let l = left.childNodes
//     let r = right.childNodes
//     fail = 0

//     setID(l, r)
//     for (i = 0; i < l.length; i++) {
//         if (i >= r.length) break
//         let ll = l[i].innerHTML.replaceAll(/<\/?[^>]+(>|$)/g, "").replaceAll("&nbsp;", " ").replaceAll("...", "").replaceAll(/  +/g, ' ').replace(/\s+$/, '').split(" ")
//         let rr = r[i].innerHTML.replaceAll(/<\/?[^>]+(>|$)/g, "").replaceAll("&nbsp;", " ").replaceAll("...", "").replaceAll(/  +/g, ' ').replace(/\s+$/, '').split(" ")

//         // console.log(r[i].innerHTML.replaceAll(/<[^>]*>?/gm, '').replaceAll("&nbsp;", " "))
//         // console.log(rr)

//         rr = seqMode(rr, ll)
//         // rr = countMode(rr, ll)
//         let new_str = ""
//         for (let j = 0; j < rr.length; j++) {
//             new_str += rr[j] + " "
//         }
//         r[i].innerHTML = new_str
//     }
//     let score = document.getElementById("score");
//     score.innerHTML = fail + " Fails"
// }

// function parMode(left) {
//     let l = left.innerHTML.replaceAll(/<\/?[^>]+(>|$)/g, "").replaceAll("&nbsp;", " ").replaceAll("...", "").replaceAll(/  +/g, ' ').replace(/\s+$/, '')
//     console.log(l)
// }

// function seqMode(rr, ll) {
//     let l_index = 0
//     let f = false
    
//     for (let j = 0; j < rr.length; j++) {
//         let r_stand = rr[j].replaceAll(",", "").replaceAll(".", "").replaceAll(" ", "").replaceAll("’", "'").toLowerCase()
//         for (z = l_index; z < ll.length; z++) {
//             let l_stand = ll[z].replaceAll(",", "").replaceAll(".", "").replaceAll(" ", "").replaceAll("’", "'").toLowerCase()
//             if (r_stand == l_stand) {
//                 l_index = z + 1
//                 f = false
//                 break
//             } else {
//                 if (!f) {
//                     f = true
//                     rr[j] = "... " + rr[j]
//                     fail+= 1
//                 }
//             }
//             if (z == ll.length - 1) {
//                 rr[j] = "<b>" + rr[j].replaceAll("... ", "") + "</b>"
//                 fail+= 1
//             }
//         }
//     }
//     return rr
// }

// function countMode(rr, ll) {
//     let tg = []
//     for (let i = 0; i < rr.length; i++) 
//         tg.push(-1)

//     for (let i = 0; i < rr.length; i++) {
//         let r_stand = rr[i].replaceAll(",", "").replaceAll(".", "").replaceAll(" ", "").replaceAll("’", "'").toLowerCase()
//         for (let j = 0; j < ll.length; j++) {
//             let l_stand = ll[j].replaceAll(",", "").replaceAll(".", "").replaceAll(" ", "").replaceAll("’", "'").toLowerCase()
//             if (l_stand == r_stand) {
//                 tg[i] = j
//                 ll[j] = "&&"
//                 break
//             }
//         }
//     }

//     let m = true
//     while (m) {
//         m  = false
//         for (let i = 0; i < rr.length - 1; i++) {
//             for (let j = i+1; j < rr.length; j++) {
//                 if (tg[j] != -1 && tg[i] > tg[j]) {
//                     tg[j] = -1
//                     m = true
//                     break
//                 }
//             }
//         }
//     }
    

//     let c = 0
//     for (let i = 0; i < tg.length; i++) {
//         if (tg[i] == -1) {
//             rr[i] = "<b>" + rr[i] + "</b>"
//             c += 1
//         } else {
//             if (tg[i] == c) {
//                 c += 1
//             } else {
//                 c = tg[i] + 1
//                 rr[i] = "... " + rr[i]
//             }
//         }
//     }
//     if (tg[tg.length - 1] < ll.length - 1)
//         if (rr[rr.length - 1][0] != '<')
//             rr[rr.length - 1] = rr[rr.length - 1] + "... "
//     return rr
// }

// function setID(l, r) {
//     for (let i = 0; i < l.length; i++) {
//         l[i].setAttribute("id", "l" + i)
//     }
//     for (let i = 0; i < r.length; i++) {
//         r[i].setAttribute("id", "r" + i)
//         $('#r' + i).hover(function() {
//             tg = "#" + this.id.replaceAll("r", "l")
//             $(tg).css('background-color', ' rgb(230, 200, 236)');
//           }, function() {
//             tg = "#" + this.id.replaceAll("r", "l")
//             $(tg).css('background-color', '');
//           });
//     }
// }

function load() {
    var fileToLoad = document.getElementById("file-upload").files[0];

    var fileReader = new FileReader();
    fileReader.onload = function(fileLoadedEvent){
        var xmlDoc = fileLoadedEvent.target.result;
        
        let left = document.getElementById("topic");
        let right = document.getElementById("ans");

        // xmlhttp=new XMLHttpRequest();
    
        // xmlhttp.open("GET","save.txt",false);
        // xmlhttp.send();
        // xmlDoc=xmlhttp.responseText;
        xmlDoc = xmlDoc.split("%break%")
        left.innerHTML = xmlDoc[0]
        right.innerHTML = xmlDoc[1]
        eng = xmlDoc[2].split(",")
        vi = xmlDoc[3].split(",")
        fail = xmlDoc[4]
    };
    fileReader.readAsText(fileToLoad, "UTF-8");
}

function save() {
    let left = document.getElementById("topic");
    let right = document.getElementById("ans");
    out = left.innerHTML + "%break%"
         + right.innerHTML + "%break%"
         + eng + "%break%"
         + vi + "%break%"
         + fail
    download(out, "save.txt", "text/plain")
}