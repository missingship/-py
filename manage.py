from flask import Flask, request, make_response, jsonify
import requests
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, String, Integer, ForeignKey, Date, Text, Boolean, true,false
from sqlalchemy import and_, or_
import json
from flask_apscheduler import APScheduler
import pandas as pd
import numpy as np
import random
#授权后写文章的时候我需要用户的头像和名字，我要把他们放到数据库中，名字最好是一授权就给我
#前端检查不准发空帖子，板块标题没写不准确定

app = Flask(__name__)
app.config.from_object('config')
app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+cymysql://rogerxlz:skeyjanexlz@localhost:3306/weixin"
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
db = SQLAlchemy(app)


class UserInformation(db.Model):
    session_id = db.Column(String(50),primary_key=True,nullable=False)
    #学校信息
    university = db.Column(String(20))
    college = db.Column(String(20))
    major = db.Column(String(20))
    grade = db.Column(String(10))
    degree = db.Column(Integer,default=0)    #1本科2硕士3博士
    #个人信息
    name = db.Column(String(20),default='未知名用户')
    gender = db.Column(Integer,default=0)       #1男2女
    PersonalWeb = db.Column(String(30))
    introduction = db.Column(Text)
    headurl = db.Column(Text)  #用户头像
    kmeans_category = db.Column(Integer)   #用于表示用户聚类结果，例如分为五类，则12345表示



#帖子表，每一个实例对应一篇帖子
class PostLibrary(db.Model):
    id = db.Column(Integer, primary_key=True,autoincrement=True)   #给每篇文章自动编个号
    theme = db.Column(String(10))          #帖子的主题，在写的时候确定，决定改帖子属于哪一个板块
    session_id = db.Column(String(50))    #作者的session_id
    name = db.Column(String(20))        #作者的名字
    title = db.Column(String(20))          #文章标题
    summary = db.Column(String(200))   #摘要指文章的前70个字
    article = db.Column(Text)
    zan_count = db.Column(Integer,default=0)   #用于统计该文章点赞数
    comment_count = db.Column(Integer,default=0)#用于统计该文章评论数
    heat = db.Column(Integer,default=0)        #该文章的每日热度

#这个表用来存储文章的点赞信息，一次点赞的点赞人和他对应的点赞文章构成一个实例
class MidZan(db.Model):
    mid_zan_id = db.Column(Integer, primary_key=True, autoincrement=True)  #应该没啥用的代理主键
    session_id = db.Column(String(50),nullable=False)
    post_id = db.Column(Integer)
    #title = db.Column(String(20))   #暂时规定一个用户不能有重名文章  因此用session和title来确定是哪一篇帖子


#评论表，一个实例对应一个用户在一篇文章下的一次评论，表包含了全部每篇文章的全部评论
class MidComment(db.Model):
    mid_comment_id = db.Column(Integer, primary_key=True, autoincrement=True)  # 代理主键
    session_id = db.Column(String(50),nullable=False)
    post_id = db.Column(Integer)
    name = db.Column(String(50))
    headurl = db.Column(Text)
    comment = db.Column(Text)                      #后续要考虑对评论的字数限制，包括上限和下限,大后期优化可以增加对垃圾评论筛除(算法)
    object_comment_id = db.Column(Integer,default=0)           #评论的回复对象的评论id
    comment_zan_count = db.Column(Integer,default=0)       #评论的点赞数

#评论点赞表
class CommentZan(db.Model):
    commentzan_id = db.Column(Integer,primary_key=True,autoincrement=True)  #代理主键
    session_id = db.Column(String(50),nullable=False)
    mid_comment_id = db.Column(Integer,nullable=False)

#记录每个用户的兴趣爱好
class Interest(db.Model):
    session_id = db.Column(String(50),primary_key=True,nullable=False)
    job = db.Column(Integer,default=0)   #招聘信息
    competition = db.Column(Integer,default=0)   #竞赛
    technology = db.Column(Integer,default=0)   #技术
    freshman = db.Column(Integer,default=0)     #大一
    interview = db.Column(Integer,default=0)    #面试
    master =  db.Column(Integer,default=0)      #研究生
    abroad = db.Column(Integer,default=0)       #出国
    organization = db.Column(Integer,default=0) #各种团体


db.create_all()


#登录
#登陆的时候获取了用户的微信名字要把微信名字给我，设定成name的初始值，后面修改再覆盖
@app.route('/login/', methods=['POST'])
def login():
    code = request.form['code']
    # 访问api获得用户的openid
    appid = "wxa76bd70f187432a9"
    secret = "eb08b38f0ec2d0b12d9377c0a04c2732"
    r = requests.get('https://api.weixin.qq.com/sns/jscode2session?'
                        'appid=%s&secret=%s&js_code=%s'
                        '&grant_type=authorization_code'%(appid, secret, code))
    if r.json()['openid']:
        #print(r.json())
        open_id = r.json()['openid']
        session_id = open_id          #hashlib模块加载不起，我决定直接用open_id
        #session_id = hashlib.md5(open_id.encode(encoding='UTF-8')).hexdigest()
        #print("密文", session_id)
        # 查找数据库，获取到的是一个对象列表，若没在数据库中添加新用户
        if UserInformation.query.filter_by(session_id=session_id).all():
                #print("已经存在")
                pass
        else:
            #print("不存在")
            user_base = UserInformation(session_id=session_id)
            userinterest = Interest(session_id=session_id)
            db.session.add(userinterest)
            db.session.add(user_base)
            db.session.commit()
        response = make_response(jsonify({'session_id': session_id}), 200)
    else:
        response = make_response(" ", 404)
    return response


#用户授权过后把信息返回给后端
@app.route('/auth/',methods=['POST'])
def auth():
    session_id = request.form['session_id']
    userInfo = json.loads(request.form['userInfo'])
    name = userInfo['nickName']
    headurl = userInfo['avatarUrl']
    UserInformation1 = UserInformation.query.filter_by(session_id=session_id).one()
    #授权后修改name仅针对没改过名字的用户，若用户自己改过名字，则不修改
    if UserInformation1.name == "未知名用户":
        UserInformation1.name = name
        MidComment1 = MidComment.query.filter_by(session_id=session_id).all()
        for i in MidComment1:
            i.name = name
        PostLibrary1 = PostLibrary.query.filter_by(session_id=session_id).all()
        for i in PostLibrary1:
            i.name = name
    UserInformation1.headurl = headurl
    db.session.commit()
    return (" ",200)

#获得用户信息用于渲染“个人信息”界面
@app.route('/getPersonalInfo/',methods=['POST'])
def getPersonalInfo():
    #还要把对应用户写的全部帖子信息返回
    session_id = request.form['session_id']
    if UserInformation.query.filter_by(session_id=session_id).one():
        personal = UserInformation.query.filter_by(session_id=session_id).one()
        PersonalInfo = {
            'name': personal.name,
            'genderIndex': personal.gender,    #性别在数据库中  0是空值  1男2女
            'PersonalWeb': personal.PersonalWeb,
            'introduction': personal.introduction
        }
        response = make_response(jsonify(PersonalInfo),200)
        return response
    else:
        return make_response(" ",404)


#获得用户信息用于渲染“学校信息”界面
@app.route('/getSchoolInfo/',methods=['POST'])
def getSchoolInfo():
    session_id = request.form['session_id']
    if UserInformation.query.filter_by(session_id=session_id).one():
        schoolInfo = UserInformation.query.filter_by(session_id=session_id).one()
        SchoolInfo = {
            'university': schoolInfo.university,
            'college': schoolInfo.college,
            'major': schoolInfo.major,
            'grade': schoolInfo.grade,
            'degreeIndex': schoolInfo.degree
        }
        response = make_response(jsonify(SchoolInfo),200)
        return response
    else:
        return make_response(" ",404)


#获得用户信息用于渲染“已发表的帖子”界面
@app.route('/getOwnPost/',methods=['POST'])
def getOwnPost():
    #注意：现在的版本是直接把该用户所有发过的帖子返回给前端，没有考虑下拉刷新
    session_id = request.form['session_id']
    users = []
    if PostLibrary.query.filter_by(session_id=session_id).all():
        outputs = PostLibrary.query.filter_by(session_id=session_id).all()
        for output in outputs:
            mid = UserInformation.query.filter_by(session_id=output.session_id).one()
            headurl = mid.headurl
            users.append({
                "name": output.name,
                "title": output.title,
                "id":output.id,
                "summary": output.summary,
                "zan_count": output.zan_count,
                "comment_count": output.comment_count,
                "headurl": headurl
            })
        #返回的是一个列表，其中的元素是字典，每一个文章对应一个字典
        #统计个数放在了列表的最末尾，但我仍然建议个数统计放在前端用len得到，放在后端显得结构混乱
    return make_response(jsonify(users),200)




#用户修改个人资料
@app.route('/setUserInformation1/',methods=['POST'])
def setUserInformation1():
    if request.form:
        session_id = request.form['session_id']
        name = request.form['name']
        output = UserInformation.query.filter_by(session_id=session_id).one()
        output.name = name
        MidComment1 = MidComment.query.filter_by(session_id=session_id).all()
        for i in MidComment1:
            i.name = name
        PostLibrary1 = PostLibrary.query.filter_by(session_id=session_id).all()
        for i in PostLibrary1:
            i.name = name
        output.gender = request.form['genderIndex']
        output.PersonalWeb = request.form['PersonalWeb']
        output.introduction = request.form['introduction']
        db.session.commit()
        return make_response(" ",200)
    else:
        return make_response(" ",404)



#用户修改学校资料
@app.route('/setUserInformation2/',methods=['POST'])
def setUserInformation2():
    if request.form:
        session_id = request.form['session_id']
        print(request.form)
        output = UserInformation.query.filter_by(session_id=session_id).one()
        output.university = request.form['university']
        output.college = request.form['college']
        output.major = request.form['major']
        output.grade = request.form['grade']
        output.degree = request.form['degreeIndex']
        db.session.commit()
        return make_response(" ",200)
    else:
        return make_response(" ",404)



# 用户修改帖子——把帖子的内容给前端，前端显示
@app.route('/modifyPost/', methods=['POST'])
def modifyPost():
    # 暂时不能修改标题
    post_id = request.form['post_id']    #作者的名字
    if PostLibrary.query.filter_by(id=post_id).one():
        output = PostLibrary.query.filter_by(id=post_id).one()
        users = {
            "article": output.article,
            "title": output.title
        }
        return make_response(jsonify(users),200)
    return make_response(" ",404)



#把用户修改完成的帖子更新到数据库
@app.route('/savePostModification/',methods=['POST'])
def savePostModification():
    post_id = request.form['post_id']
    article = request.form['article']
    #print(article)
    if len(article)<=100:
        summary = article
    else:
        summary = article[0:100]
    output = PostLibrary.query.filter_by(id=post_id).one()
    #output.title = title
    output.article = article
    output.summary = summary
    db.session.commit()
    return make_response(" ",200)

#删除文章
@app.route('/deletePost/',methods=['POST'])
def deletePost():
    post_id = request.form['post_id']
    output = PostLibrary.query.filter_by(id=post_id).one()
    db.session.delete(output)
    MidZan1 = MidZan.query.filter_by(post_id=post_id).all()
    for i in MidZan1:
        db.session.delete(i)
    MidComment1 = MidComment.query.filter_by(post_id=post_id).all()
    for j in MidComment1:
        mid_comment_id = j.mid_comment_id
        CommentZan1 = CommentZan.query.filter_by(mid_comment_id=mid_comment_id).all()
        for k in CommentZan1:
            db.session.delete(k)
        db.session.delete(j)
    db.session.commit()
    return make_response(" ",200)



#主页热度推荐五篇文章
@app.route('/homepageRecommend/',methods=['POST'])
def homepageRecommend():
    outputs = PostLibrary.query.order_by(-PostLibrary.heat).limit(5)
    users = []
    for output in outputs:
        mid = UserInformation.query.filter_by(session_id=output.session_id).one()
        headurl = mid.headurl
        users.append({
            "name": output.name,
            "title": output.title,
            "summary": output.summary,
            "id": output.id,
            "zan_count": output.zan_count,
            "comment_count": output.comment_count,
            "headurl": headurl
        })
    return make_response(jsonify(users), 200)


#轮播推荐
@app.route('/swiperRecommend/',methods=['POST'])
def swiperRecommend():
    output1 = PostLibrary.query.order_by(-PostLibrary.heat).filter_by(theme="大一专栏").first()
    output2 = PostLibrary.query.order_by(-PostLibrary.heat).filter_by(theme="面试经验").first()
    output3 = PostLibrary.query.order_by(-PostLibrary.heat).filter_by(theme="技术栈").first()
    user = {
        "post_id1": output1.id,
        "post_id2": output2.id,
        "post_id3": output3.id
    }
    return (jsonify(user),200)


#主页聚类推荐五篇文章
@app.route('/kmeansRecommend/',methods=['POST'])
def kmeansRecommend():
    session_id = request.form['session_id']
    users = []
    UserInformation1 = UserInformation.query.filter_by(session_id=session_id).one()
    kmeans_category = UserInformation1.kmeans_category
    if UserInformation.query.filter_by(kmeans_category=kmeans_category).all():    #如果有同类的人
        outputs = UserInformation.query.filter_by(kmeans_category=kmeans_category).all()
        for output in outputs:
            mid = output.session_id   #同类的session_id
            if MidZan.query.filter_by(session_id=mid).all():   #如果同类有点过赞
                MidZan1 = MidZan.query.filter_by(session_id=mid).all()
                for i in MidZan1:
                    id = i.post_id
                    PostLibrary1 = PostLibrary.query.filter_by(id=id).one()
                    session_id1 = PostLibrary1.session_id
                    UserInformation2 = UserInformation.query.filter_by(session_id=session_id1).one()
                    users.append({
                        "name": PostLibrary1.name,
                        "title": PostLibrary1.title,
                        "summary": PostLibrary1.summary,
                        "id": PostLibrary1.id,
                        "zan_count": PostLibrary1.zan_count,
                        "comment_count": PostLibrary1.comment_count,
                        "headurl": UserInformation2.headurl
                    })
            else:
                continue
        if len(users)>=5:
            n = len(users)
            a = random.randint(0,n-5)
            b = []
            for i in range(5):
                b.append(users[a+i])
            users = b
            return make_response(jsonify(users),200)
        else:
            outputs = PostLibrary.query.order_by(-PostLibrary.zan_count).limit(5)
            users = []
            for output in outputs:
                mid = UserInformation.query.filter_by(session_id=output.session_id).one()
                headurl = mid.headurl
                users.append({
                    "name": output.name,
                    "title": output.title,
                    "summary": output.summary,
                    "id": output.id,
                    "zan_count": output.zan_count,
                    "comment_count": output.comment_count,
                    "headurl": headurl
                })
            return make_response(jsonify(users), 200)
    else:     #如果没有同类的人
        outputs = PostLibrary.query.order_by(-PostLibrary.zan_count).limit(5)
        users = []
        for output in outputs:
            mid = UserInformation.query.filter_by(session_id=output.session_id).one()
            headurl = mid.headurl
            users.append({
                "name": output.name,
                "title": output.title,
                "summary": output.summary,
                "id": output.id,
                "zan_count": output.zan_count,
                "comment_count": output.comment_count,
                "headurl": headurl
            })
        return make_response(jsonify(users), 200)




#点击进入各个板块，显示属于该板块的所有文章缩小版(作者标题摘要赞数)
@app.route('/getIntoPlate/',methods=['POST'])
def getIntoPlate():
    # 考虑实现
    #确定一页能展示多少个缩小版，一次只返回相应数量的缩小版信息
    #设置一个断点信息，保存当前显示到了哪个位置，当用户下拉刷新，再展示几个，循环往复
    #后期还可以考虑把不同板块的文章放在不同的数据表中，这样可以减少进入各个板块时的查询时间
    #分页显示的内容在FLASK WEB的个人博客的编写前台那里有
    theme = request.form['theme']
    session_id = request.form['session_id']
    increaseInterest(theme, session_id, 1)
    outputs = PostLibrary.query.filter_by(theme=theme).all()
    users = []
    for output in outputs:
        mid = UserInformation.query.filter_by(session_id=output.session_id).one()
        headurl = mid.headurl
        users.append({
            "name": output.name,
            "title": output.title,
            "summary": output.summary,
            "id": output.id,
            "zan_count": output.zan_count,
            "comment_count": output.comment_count,
            "headurl": headurl
        })
    return make_response(jsonify(users), 200)

#用于增加兴趣值
def increaseInterest(a,session_id,n):
    #a是板块的字符串,n是interest增加的数量
    Interest1 = Interest.query.filter_by(session_id=session_id).one()
    if a == "企业招聘":
        Interest1.job += n
    if a == "竞赛相关":
        Interest1.competition += n
    if a == "大一专栏":
        Interest1.freshman += n
    if a == "面试经验":
        Interest1.interview += n
    if a == "海外留学":
        Interest1.abroad += n
    if a == "技术栈":
        Interest1.technology += n
    if a == "团队组建":
        Interest1.organization += n
    if a == "考验宝典":
        Interest1.master += n
    db.session.commit()

#用户点击查看对应帖子
@app.route('/readPost/',methods=['POST'])
def readPost():
    id = request.form['id']    #帖子的id
    session_id = request.form['session_id']    #读者的session_id
    test = PostLibrary.query.filter_by(id=id).one()
    theme = test.theme
    increaseInterest(theme,session_id,2)
    author_session_id = test.session_id
    sign = 1
    test.heat = test.heat + 1   #用户浏览帖子则帖子热度加一
    db.session.commit()
    if PostLibrary.query.filter_by(id=id).one():
        #if MidZan.query.filter_by(post_id=id).all() and MidZan.query.filter_by(session_id=session_id).all():  #先判断MidZan表中是否有post_id存在
        if MidZan.query.filter_by(post_id=id,session_id=session_id).all():
            sign = 0   #这个标志用于表示能不能点赞，0是不能，1是可以
            #print('该用户不能对该文章点赞')
        output = PostLibrary.query.filter_by(id=id).one()      #找到要浏览的那篇帖子
        output2 = UserInformation.query.filter_by(session_id=author_session_id).one()  # 找到帖子的作者
        if output2.college and output2.university and output2.grade:  # 保证三者都有的时候
            shortintro = output2.university + output2.college + output2.grade  # 拼接学校学院年级形成一个字符串（要保证三者都不为空）
        else:
            shortintro = "暂时没有详细全面的个人信息哦"
        mid = UserInformation.query.filter_by(session_id=output.session_id).one()
        headurl = mid.headurl
        users = {
            "headurl": headurl,
            "shortintro": shortintro,
            "name": output.name,
            "title": output.title,
            "article": output.article,
            "zan_count": output.zan_count,
            "comment_count": output.comment_count,
            "sign": sign
        }
        return make_response(jsonify(users),200)
    return make_response(" ",404)




#查看评论区
@app.route('/readComment/',methods=['POST'])
def readComment():
    post_id = request.form['post_id']
    session_id = request.form['session_id']
    #点击评论区则热度加3
    PostLibrary1 = PostLibrary.query.filter_by(id = post_id).one()
    PostLibrary1.heat = PostLibrary1.heat + 3
    db.session.commit()
    outputs = MidComment.query.order_by(-MidComment.comment_zan_count).filter_by(post_id = post_id).all()
    user = []
    for output in outputs:
        sign = 1           #标记该用户是否能对该评论点赞，1是可以，0是不可以
        mid_comment_id = output.mid_comment_id
        if CommentZan.query.filter_by(mid_comment_id=mid_comment_id).all() and CommentZan.query.filter_by(session_id=session_id).all():
            if CommentZan.query.filter_by(mid_comment_id=mid_comment_id,session_id=session_id):
                sign = 0   #标志着该用户不能对该评论点赞
        object_comment_id = output.object_comment_id
        if object_comment_id == 0:
            object_name = ""
        else:
            mid = MidComment.query.filter_by(mid_comment_id = object_comment_id).one()
            object_name = mid.name
        user.append({
            "name": output.name,             #评论者姓名
            "comment": output.comment,       #评论内容
            "headurl":output.headurl,        #评论者头像
            "object_name":object_name,         #评论回复对象的名字
            "sign": sign,                    #能否点赞标志，0是不能点赞
            "mid_comment_id":mid_comment_id, #评论的标志id，用于后续点赞的时候返给后端
            "comment_zan_count": output.comment_zan_count
        })
    return make_response(jsonify(user),200)





#用户写帖子
@app.route('/writePose/',methods=['POST'])
def writePose():
    session_id = request.form['session_id']
    title = request.form['title']
    article = request.form['article']
    theme = request.form['theme']
    output = UserInformation.query.filter_by(session_id=session_id).one()
    name = output.name
    if len(article)<=100:
        summary = article
    else:
        summary = article[0:100]
    PostLibrary1 = PostLibrary(session_id=session_id,title=title,article=article,theme=theme,name=name,summary=summary,zan_count=0,comment_count=0,heat=0)
    db.session.add(PostLibrary1)
    db.session.commit()
    return make_response(" ",200)






#主页搜索功能
#主页搜索只有一个keyword，分板块的搜索还要再给我一个theme
@app.route('/search/',methods=['POST'])
def search():
    #当前是简易版本，只对文章标题和前七十字进行检索
    #没想好怎么让搜索到的内容分页显示（下拉刷新）
    key_word = request.form['key_word']
    outputs = PostLibrary.query.filter(or_(PostLibrary.summary.like('%'+key_word+'%'),PostLibrary.title.like('%'+key_word+'%'),PostLibrary.name.like('%'+key_word+'%'),PostLibrary.article.like('%'+key_word+'%'))).all()
    user = []
    for output in outputs:
        mid = UserInformation.query.filter_by(session_id=output.session_id).one()
        headurl = mid.headurl
        user.append({
            "name": output.name,
            "title": output.title,
            "summary": output.summary,
            "session_id": output.session_id,
            "id": output.id,
            "zan_count": output.zan_count,
            "comment_count": output.comment_count,
            "headurl": headurl
        })
    return make_response(jsonify(user),200)


#对相应的文章点赞功能
@app.route('/praise/',methods=['POST'])
def praise():
    session_id = request.form['session_id']
    post_id = request.form['post_id']
    #文章点赞数统计加一
    PostLibrary1 = PostLibrary.query.filter_by(id=post_id).one()
    PostLibrary1.zan_count = PostLibrary1.zan_count + 1
    # 点赞一篇文章相当于热度加三
    PostLibrary1.heat = PostLibrary1.heat + 3
    #兴趣度加三
    theme = PostLibrary1.theme
    increaseInterest(theme, session_id, 3)
    #点赞表增加一个实例
    MidZan1 = MidZan(post_id=post_id,session_id=session_id)
    db.session.add(MidZan1)
    db.session.commit()
    return make_response(" ",200)


#添加评论功能
@app.route('/writeComment/',methods=['POST'])
def writeComment():
    session_id = request.form['session_id']
    post_id = request.form['post_id']
    comment = request.form['comment']
    object_comment_id = request.form['object_comment_id']
    output = UserInformation.query.filter_by(session_id = session_id).one()
    name = output.name
    headurl = output.headurl
    #评论数统计加一
    PostLibrary1 = PostLibrary.query.filter_by(id = post_id).one()
    PostLibrary1.comment_count = PostLibrary1.comment_count + 1
    #热度加5
    PostLibrary1.heat = PostLibrary1.heat + 5
    #兴趣度加3
    theme = PostLibrary1.theme
    increaseInterest(theme, session_id, 3)
    #添加评论实例
    comment1 = MidComment(post_id = post_id,session_id = session_id,comment = comment,name = name,object_comment_id=object_comment_id,headurl=headurl)
    db.session.add(comment1)
    db.session.commit()
    return make_response(" ",200)

#给相应的评论点赞
@app.route('/praiseComment/',methods=['POST'])
def praiseComment():
    session_id = request.form['session_id']
    mid_comment_id = request.form['mid_comment_id']
    #评论点赞表增加一个实例
    CommentZan1 = CommentZan(session_id=session_id,mid_comment_id=mid_comment_id)
    #评论点赞数量加一
    MidComment1 = MidComment.query.filter_by(mid_comment_id=mid_comment_id).one()
    MidComment1.comment_zan_count = MidComment1.comment_zan_count + 1
    db.session.add(CommentZan1)
    db.session.commit()
    return make_response(" ",200)

#用于kmeans
def assignment(df,centroids):
    for i in centroids.keys():
        #.keys()等于k  就是字典中值得数量
        df['distance_from_{}'.format(i)]=np.sqrt(
        (df['a']-centroids[i][0])**2+(df['b']-centroids[i][1])**2+(df['c']-centroids[i][2])**2+(df['d']-centroids[i][3])**2+(df['e']-centroids[i][4])**2+(df['f']-centroids[i][5])**2+(df['g']-centroids[i][6])**2+(df['h']-centroids[i][7])**2
        )
        name=['distance_from_{}'.format(i) for i in centroids]
        #后面的for是避免每一次大的for循环不停地建立覆盖name列
    df['closest']=df.loc[:,name].idxmin(axis=1)
    #比较距离并存储距离最小的那个类名，loc定位从name那三个列开始比较，axis是一个参数=1表示横向比较
    df['closest']=df['closest'].map(lambda x:int(x.lstrip('distance_from_{}')))
    return df

#给用户分类
def kmeans():
    outputs = Interest.query.filter(Interest.session_id!= "").all()
    num = Interest.query.filter(Interest.session_id!="").count()    #统计有多少个实例
    session_id = []
    job = []
    competition = []
    technology = []
    freshman = []
    interview = []
    master = []
    abroad = []
    organization = []
    sum = 0   #用于计算合理的随机点，所有兴趣度的平均
    for output in outputs:
        session_id.append(output.session_id)
        job.append(output.job)
        competition.append(output.competition)
        technology.append(output.technology)
        freshman.append(output.freshman)
        interview.append(output.interview)
        master.append(output.master)
        abroad.append(output.abroad)
        organization.append(output.organization)
        sum = sum + output.job + output.competition + output.technology + output.freshman + output.interview + output.master + output.abroad + output.organization
    df = pd.DataFrame({
        'session_id': session_id,
        'a': job,
        'b': competition,
        'c': technology,
        'd': freshman,
        'e': interview,
        'f': master,
        'g': abroad,
        'h': organization
    })
    k = 3
    n = int(sum/8/num)   #设定随机数的阈值
    centroids = {
        i + 1: [np.random.randint(0, n), np.random.randint(0, n), np.random.randint(0, n), np.random.randint(0, n),
                np.random.randint(0, n), np.random.randint(0, n), np.random.randint(0, n), np.random.randint(0, n)]
        for i in range(k)  # 循环一次完了就向上跳重复一次，本语句是得到三个随机点
    }
    df = assignment(df, centroids)
    while True:
        old_closest = df['closest']
        for i in centroids.keys():
            centroids[i][0] = np.mean(df[df['closest'] == i]['a'])
            centroids[i][1] = np.mean(df[df['closest'] == i]['b'])
            centroids[i][2] = np.mean(df[df['closest'] == i]['c'])
            centroids[i][3] = np.mean(df[df['closest'] == i]['d'])
            centroids[i][4] = np.mean(df[df['closest'] == i]['e'])
            centroids[i][5] = np.mean(df[df['closest'] == i]['f'])
            centroids[i][6] = np.mean(df[df['closest'] == i]['g'])
            centroids[i][7] = np.mean(df[df['closest'] == i]['h'])
        df = assignment(df, centroids)
        if old_closest.equals(df['closest']):
            break
    for output in outputs:
        session_id = output.session_id
        closest = int(df[df['session_id']==session_id]['closest'])   #强制转换成int类型，不然好像还是表格的样子
        UserInformation1 = UserInformation.query.filter_by(session_id=session_id).one()
        UserInformation1.kmeans_category = closest
    db.session.commit()


#用来设置定时任务的定时器
#定时根据Interest表计算每个用户的聚类，更新userInformation表的kmeans_category
#def job_func():
    #with app.app_context():
        #PostLibrary1 = PostLibrary.query.filter_by(heat = 8).one()
        #print(PostLibrary1.heat)


#这个只是用来测试是否能在服务器访问的
@app.route('/aaa/')
def aaa():
    return 'I dont love you anymore'

if __name__ == "__main__":
    #生产环境 nginx+uwsgi if name的作用在于防止加载两个服务器
    #下面三行是用来设置定时的
    #scheduler = APScheduler()
    #scheduler.init_app(app)
    #scheduler.start()
    #n = PostLibrary.query.filter(PostLibrary.session_id!="").count()
    app.run()
